"""Cross-table consistency, measure contracts and report structure checks."""

import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import unittest
from scripts.generate_data import generate, AS_OF
from scripts.build_powerbi import RELATIONS, MEASURES, PAGES
from scripts.reconcile_metrics import metrics, load, CONTEXTS
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = generate()

    def test_reproducible_exports_and_checksums(self):
        manifest = json.loads((ROOT / "data/processed/manifest.json").read_text())
        self.assertEqual(self.tables, generate())
        for table, rows in self.tables.items():
            path = ROOT / "data/processed" / f"{table}.csv"
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                manifest["tables"][table]["sha256"],
            )
            with path.open() as f:
                actual = list(csv.DictReader(f))
            expected = [
                {k: "" if v is None else str(v) for k, v in row.items()} for row in rows
            ]
            self.assertEqual(actual, expected)

    def test_every_foreign_key_links_to_same_participants(self):
        t = self.tables
        for a, c, b, d, _ in RELATIONS:
            parents = {r[d] for r in t[b]}
            self.assertTrue(all(r[c] is None or r[c] in parents for r in t[a]), (a, c))
        appointments = {r["AppointmentID"]: r for r in t["Appointment"]}
        records = {r["RecordID"]: r for r in t["Medical_Record"]}
        doctors = {r["DoctorID"]: r for r in t["Doctor"]}
        for r in records.values():
            a = appointments[r["AppointmentID"]]
            self.assertEqual(
                (r["PatientID"], r["DoctorID"], r["VisitDate"]),
                (a["PatientID"], a["DoctorID"], a["AppointmentDate"]),
            )
            self.assertEqual(a["Status"], "Completed")
            self.assertEqual(doctors[a["DoctorID"]]["DepartmentID"], a["DepartmentID"])
        for r in t["Billing"]:
            self.assertEqual(r["PatientID"], records[r["RecordID"]]["PatientID"])

    def test_schedule_and_snapshot_outcomes(self):
        for key in ["DoctorID", "PatientID"]:
            used = set()
            for r in self.tables["Appointment"]:
                if r["Status"] == "Cancelled":
                    continue
                slot = (r[key], r["AppointmentDate"], r["AppointmentTime"])
                self.assertNotIn(slot, used)
                used.add(slot)
        for r in self.tables["Appointment"]:
            self.assertEqual(
                r["Status"] == "Scheduled",
                date.fromisoformat(r["AppointmentDate"]) > AS_OF,
            )

    def test_prescriptions_and_payments_agree(self):
        prescriptions = {}
        meds = {r["MedicineID"]: r["MedicineName"] for r in self.tables["Medicine"]}
        for r in self.tables["Prescription"]:
            prescriptions.setdefault(r["RecordID"], []).append(meds[r["MedicineID"]])
        for r in self.tables["Medical_Record"]:
            self.assertEqual(
                r["Prescription"],
                " | ".join(prescriptions.get(r["RecordID"], [])) or "No prescription",
            )
        for r in self.tables["Billing"]:
            self.assertGreaterEqual(r["TotalAmount"], 0)
            if r["PaymentStatus"] == "Paid":
                self.assertTrue(r["PaymentMethod"])
                self.assertLessEqual(date.fromisoformat(r["PaymentDate"]), AS_OF)
            else:
                self.assertIsNone(r["PaymentDate"])
                self.assertIsNone(r["PaymentMethod"])

    def test_room_stays_have_no_overlap_and_reconcile_snapshot(self):
        stays = self.tables["Room_Assignment"]
        self.assertTrue(stays)
        for key in ["RoomID", "PatientID"]:
            ids = {r[key] for r in stays}
            for identifier in ids:
                rows = sorted(
                    [r for r in stays if r[key] == identifier],
                    key=lambda r: r["AdmissionDate"],
                )
                for first, second in zip(rows, rows[1:]):
                    self.assertIsNotNone(first["DischargeDate"])
                    self.assertLessEqual(
                        first["DischargeDate"], second["AdmissionDate"]
                    )
        active = {r["RoomID"] for r in stays if r["DischargeDate"] is None}
        self.assertEqual(
            active,
            {
                r["RoomID"]
                for r in self.tables["Room"]
                if r["AvailabilityStatus"] == "Occupied"
            },
        )

    def test_pediatric_patients_are_children_at_encounter(self):
        patients = {r["PatientID"]: r for r in self.tables["Patient"]}
        pediatric = [r for r in self.tables["Appointment"] if r["DepartmentID"] == 2]
        self.assertTrue(pediatric)
        for r in pediatric:
            birth = date.fromisoformat(patients[r["PatientID"]]["DateOfBirth"])
            day = date.fromisoformat(r["AppointmentDate"])
            self.assertLess(
                day.year
                - birth.year
                - ((day.month, day.day) < (birth.month, birth.day)),
                18,
            )

    def test_active_relationships_have_no_multiple_filter_paths(self):
        graph = {t: [] for t in self.tables}
        for a, _, b, _, active in RELATIONS:
            if active:
                graph[b].append(a)
        for root in graph:
            found = set()

            def walk(node):
                for child in graph[node]:
                    self.assertNotIn(child, found, (root, child))
                    found.add(child)
                    walk(child)

            walk(root)

    def test_every_visual_field_exists_and_layout_stays_on_page(self):
        model = json.loads(
            (ROOT / "PowerBI/Hospital.SemanticModel/model.bim").read_text()
        )["model"]
        columns = {
            t["name"]: {c["name"] for c in t["columns"]} for t in model["tables"]
        }
        measures = {
            t["name"]: {m["name"] for m in t.get("measures", [])}
            for t in model["tables"]
        }
        pages = ROOT / "PowerBI/Hospital.Report/definition/pages"
        self.assertEqual(len(list(pages.glob("*/page.json"))), 5)
        for p in pages.glob("*/visuals/*/visual.json"):
            visual = json.loads(p.read_text())
            pos = visual["position"]
            self.assertLessEqual(pos["x"] + pos["width"], 1280)
            self.assertLessEqual(pos["y"] + pos["height"], 720)
            for role in (
                visual["visual"].get("query", {}).get("queryState", {}).values()
            ):
                for projection in role["projections"]:
                    kind, expr = next(iter(projection["field"].items()))
                    table = expr["Expression"]["SourceRef"]["Entity"]
                    name = expr["Property"]
                    self.assertIn(
                        name, (measures if kind == "Measure" else columns)[table]
                    )

    def test_visual_roles_navigation_and_spacing(self):
        pages = ROOT / "PowerBI/Hospital.Report/definition/pages"
        page_ids = {p.parent.name for p in pages.glob("*/page.json")}
        allowed = {
            "cardVisual": {"Data"},
            "slicer": {"Values"},
            "clusteredBarChart": {"Category", "Y"},
            "clusteredColumnChart": {"Category", "Y"},
            "lineChart": {"Category", "Y"},
            "donutChart": {"Category", "Y"},
            "textbox": set(),
            "actionButton": set(),
        }
        for page in page_ids:
            boxes = []
            for p in (pages / page).glob("visuals/*/visual.json"):
                d = json.loads(p.read_text())
                v, box = d["visual"], d["position"]
                kind = v["visualType"]
                self.assertEqual(
                    set(v.get("query", {}).get("queryState", {})), allowed[kind]
                )
                if kind == "actionButton":
                    target = v["visualContainerObjects"]["visualLink"][0]["properties"][
                        "navigationSection"
                    ]["expr"]["Literal"]["Value"].strip("'")
                    self.assertIn(target, page_ids)
                    self.assertGreaterEqual(box["height"], 40)
                if kind == "slicer":
                    self.assertGreaterEqual(box["height"], 80)
                    self.assertEqual(
                        v["objects"]["data"][0]["properties"]["mode"]["expr"][
                            "Literal"
                        ]["Value"],
                        "'Dropdown'",
                    )
                self.assertGreaterEqual(box["x"], 0)
                self.assertGreaterEqual(box["y"], 0)
                for name, other in boxes:
                    overlap = (
                        box["x"] < other["x"] + other["width"]
                        and other["x"] < box["x"] + box["width"]
                        and box["y"] < other["y"] + other["height"]
                        and other["y"] < box["y"] + box["height"]
                    )
                    self.assertFalse(overlap, (page, p.parent.name, name))
                boxes.append((p.parent.name, box))

    def test_charts_are_distinct_readable_and_snapshot_safe(self):
        seen = {}
        for page, _, _, charts in PAGES:
            for _, title, _, category, measures in charts:
                key = (category, tuple(measures))
                self.assertNotIn(key, seen, (page, title, seen.get(key)))
                seen[key] = (page, title)
                if category == "Month":
                    # Jan 2026 holds only future bookings: monthly trends must not
                    # count them, or the last month looks like a collapse.
                    self.assertFalse(
                        {"Appointments", "Scheduled appointments"} & set(measures),
                        title,
                    )
        doctors = len(list(csv.DictReader((ROOT / "data/processed/Doctor.csv").open())))
        pages = ROOT / "PowerBI/Hospital.Report/definition/pages"
        for p in pages.glob("*/visuals/chart*/visual.json"):
            d = json.loads(p.read_text())
            category = d["visual"]["query"]["queryState"]["Category"]["projections"][0]
            if category["nativeQueryRef"] == "Doctor name":
                # About 16 px per bar after the title, so all doctors fit unscrolled.
                self.assertGreaterEqual(d["position"]["height"] - 40, doctors * 15)

    def test_theme_series_colors_have_graphic_contrast(self):
        def luminance(color):
            channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
            r, g, b = [
                c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                for c in channels
            ]
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        theme = json.loads(
            (
                ROOT
                / "PowerBI/Hospital.Report/StaticResources/RegisteredResources/Clinical.json"
            ).read_text()
        )
        for color in theme["dataColors"]:
            ratio = (1.05) / (luminance(color) + 0.05)
            self.assertGreaterEqual(ratio, 3.0, color)

    def test_accessibility_alt_text_tooltips_and_tab_order(self):
        def text(prop):
            return prop["expr"]["Literal"]["Value"].strip("'")

        pages = ROOT / "PowerBI/Hospital.Report/definition/pages"
        for page in pages.glob("*/page.json"):
            visuals = [
                json.loads(p.read_text())
                for p in page.parent.glob("visuals/*/visual.json")
            ]
            for d in visuals:
                objects = d["visual"]["visualContainerObjects"]
                alt = text(objects["general"][0]["properties"]["altText"])
                self.assertTrue(alt.strip(), d["name"])
                self.assertLessEqual(len(alt), 150, d["name"])
                if d["visual"]["visualType"] == "actionButton":
                    tooltip = text(objects["visualLink"][0]["properties"]["tooltip"])
                    self.assertTrue(tooltip.strip(), d["name"])
            # Power BI focuses the highest tabOrder first: reading order
            # (top to bottom, then left to right) must have descending values.
            reading = sorted(
                visuals, key=lambda d: (d["position"]["y"], d["position"]["x"])
            )
            orders = [d["position"]["tabOrder"] for d in reading]
            self.assertEqual(orders, sorted(orders, reverse=True), page.parent.name)
            self.assertEqual(len(set(orders)), len(orders), page.parent.name)
            self.assertEqual(reading[0]["name"], "heading")

    def test_metric_oracle_cohorts_blanks_and_resource_scope(self):
        tables = load()
        cases = {c["name"]: metrics(tables, c) for c in CONTEXTS}
        all_metrics = cases["All"]
        self.assertEqual(set(all_metrics), set(MEASURES))
        self.assertEqual(all_metrics["Appointments"], 4338)
        self.assertEqual(all_metrics["Collected amount"], Decimal("1960519.62"))
        self.assertEqual(
            all_metrics["Billed amount"],
            all_metrics["Collected amount"] + all_metrics["Outstanding amount"],
        )
        for scenario in [
            "2026-01",
            "1900-01",
            "Scheduled only",
            "Conflicting doctor department",
        ]:
            self.assertIsNone(cases[scenario]["Completed appointments"])
            self.assertIsNone(cases[scenario]["Billed amount"])
            self.assertIsNone(cases[scenario]["Completion rate"])
        self.assertEqual(cases["Completed only"]["Cancellation rate"], 0)
        self.assertEqual(cases["Cancelled only"]["Completion rate"], 0)
        self.assertEqual(cases["2026-01"]["Rooms"], all_metrics["Rooms"])
        self.assertEqual(
            cases["2026-01"]["Department doctors"], all_metrics["Department doctors"]
        )
        self.assertIsNone(cases["Conflicting doctor department"]["Department doctors"])
        self.assertEqual(
            cases["Pediatrics December"]["Rooms"], cases["Department 2"]["Rooms"]
        )

    def test_kpi_oracles_do_not_multiply_bills_when_joining(self):
        visits = {r["RecordID"]: r for r in self.tables["Medical_Record"]}
        appts = {r["AppointmentID"]: r for r in self.tables["Appointment"]}
        by_department = {i: 0 for i in range(1, 6)}
        paid = 0
        for bill in self.tables["Billing"]:
            if bill["PaymentStatus"] != "Paid":
                continue
            paid += bill["TotalAmount"]
            dept = appts[visits[bill["RecordID"]]["AppointmentID"]]["DepartmentID"]
            by_department[dept] += bill["TotalAmount"]
        self.assertAlmostEqual(paid, sum(by_department.values()), places=6)
        self.assertEqual(len(self.tables["Billing"]), len(visits))


if __name__ == "__main__":
    unittest.main()
