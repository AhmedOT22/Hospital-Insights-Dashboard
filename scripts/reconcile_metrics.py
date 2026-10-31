"""Generate independent CSV-based SQL and DAX acceptance cases, without a DAX engine."""

from collections import Counter
import csv
from datetime import date
from decimal import Decimal
import json
from pathlib import Path

from scripts.build_powerbi import MEASURES

ROOT = Path(__file__).resolve().parents[1]
CONTEXTS = [
    {"name": "All"},
    *({"name": f"Department {i}", "department": i} for i in range(1, 6)),
    *(
        {"name": month, "month": month}
        for month in ["2024-01", "2025-12", "2026-01", "1900-01"]
    ),
    {"name": "Doctor 1", "doctor": 1},
    {"name": "Patient 1", "patient": 1},
    {"name": "Cancelled only", "status": "Cancelled"},
    {"name": "Completed only", "status": "Completed"},
    {"name": "Scheduled only", "status": "Scheduled"},
    {"name": "Pediatrics December", "department": 2, "month": "2025-12"},
    {"name": "Conflicting doctor department", "department": 2, "doctor": 1},
]


def load():
    tables = {}
    for path in (ROOT / "data/processed").glob("*.csv"):
        with path.open(encoding="utf-8", newline="") as stream:
            tables[path.stem] = list(csv.DictReader(stream))
    return tables


def metrics(tables, context):
    """Join records by IDs; apply documented cohort versus snapshot filter scopes."""
    t, c = tables, context

    def matches(row, key, col):
        return key not in c or row[col] == str(c[key])

    appointments = [
        a
        for a in t["Appointment"]
        if matches(a, "department", "DepartmentID")
        and matches(a, "doctor", "DoctorID")
        and matches(a, "patient", "PatientID")
        and matches(a, "status", "Status")
        and ("month" not in c or a["AppointmentDate"][:7] == c["month"])
    ]
    completed = [a for a in appointments if a["Status"] == "Completed"]
    cancelled = [a for a in appointments if a["Status"] == "Cancelled"]
    scheduled = [a for a in appointments if a["Status"] == "Scheduled"]
    appointment_ids = {a["AppointmentID"] for a in appointments}
    visits = [r for r in t["Medical_Record"] if r["AppointmentID"] in appointment_ids]
    record_ids = {r["RecordID"] for r in visits}
    bills = [b for b in t["Billing"] if b["RecordID"] in record_ids]
    rooms = [r for r in t["Room"] if matches(r, "department", "DepartmentID")]
    room_ids = {r["RoomID"] for r in rooms}
    closed = [
        r
        for r in t["Room_Assignment"]
        if r["RoomID"] in room_ids
        and matches(r, "patient", "PatientID")
        and r["DischargeDate"]
    ]

    def count(rows):
        return len(rows) or None  # DAX COUNTROWS(empty) returns BLANK.

    def amount(rows):
        return (
            sum((Decimal(b["TotalAmount"]) for b in rows), Decimal(0)) if rows else None
        )

    def divide(numerator, denominator):
        return (
            None if not denominator else Decimal(numerator or 0) / Decimal(denominator)
        )

    billed = amount(bills)
    collected = amount([b for b in bills if b["PaymentStatus"] == "Paid"])
    occupied = [r for r in rooms if r["AvailabilityStatus"] == "Occupied"]
    patients = Counter(a["PatientID"] for a in completed)
    days = [
        (
            date.fromisoformat(r["DischargeDate"])
            - date.fromisoformat(r["AdmissionDate"])
        ).days
        for r in closed
    ]
    result = {
        "Appointments": count(appointments),
        "Completed appointments": count(completed),
        "Cancelled appointments": count(cancelled),
        "Scheduled appointments": count(scheduled),
        "Completion rate": divide(count(completed), len(completed) + len(cancelled)),
        "Cancellation rate": divide(count(cancelled), len(completed) + len(cancelled)),
        "Patients served": count(patients),
        "Visits": count(visits),
        "Prescriptions": count(
            [r for r in t["Prescription"] if r["RecordID"] in record_ids]
        ),
        "Billed amount": billed,
        "Collected amount": collected,
        "Outstanding amount": amount(
            [b for b in bills if b["PaymentStatus"] == "Unpaid"]
        ),
        "Collection rate": divide(collected, billed),
        "Doctors with appointments": count({a["DoctorID"] for a in appointments}),
        "Department doctors": count(
            [
                r
                for r in t["Doctor"]
                if matches(r, "department", "DepartmentID")
                and matches(r, "doctor", "DoctorID")
            ]
        ),
        "Department staff": count(
            [r for r in t["Staff"] if matches(r, "department", "DepartmentID")]
        ),
        "Rooms": count(rooms),
        "Occupied rooms": count(occupied),
        "Snapshot occupancy": divide(count(occupied), count(rooms)),
        "Completed stays": count(closed),
        "Average completed stay": divide(sum(days), len(days)) if days else None,
        "Repeat patients": count([p for p, n in patients.items() if n > 1]),
    }
    assert result.keys() == MEASURES.keys()
    return result


def number(value, blank="NULL"):
    return (
        blank if value is None else str(Decimal(value).quantize(Decimal("0.00000001")))
    )


def write():
    tables = load()
    cases = [
        {
            "context": c,
            "metrics": {m: number(v, None) for m, v in metrics(tables, c).items()},
        }
        for c in CONTEXTS
    ]
    (ROOT / "data/processed/expected_metrics.json").write_text(
        json.dumps(cases, indent=2) + "\n"
    )
    dax = []
    expected = []
    contexts = []
    filters = {
        "department": ("Department", "DepartmentID"),
        "doctor": ("Doctor", "DoctorID"),
        "patient": ("Patient", "PatientID"),
        "month": ("Appointment", "Month"),
        "status": ("Appointment", "Status"),
    }
    for c in CONTEXTS:
        contexts.append(
            "("
            + ",".join(
                "NULL"
                if c.get(k) is None
                else str(c[k])
                if isinstance(c[k], int)
                else "N'" + c[k] + "'"
                for k in ["name", "department", "doctor", "patient", "month", "status"]
            )
            + ")"
        )
        conditions = [
            f"TREATAS({{{json.dumps(v, ensure_ascii=False)}}}, '{filters[k][0]}'[{filters[k][1]}])"
            for k, v in c.items()
            if k in filters
        ]
        for m, v in metrics(tables, c).items():
            calc = (
                f"CALCULATE([{m}]"
                + (", " + ", ".join(conditions) if conditions else "")
                + ")"
            )
            dax.append(
                f'    VAR Actual = {calc}\n    VAR Expected = {number(v, "BLANK()")}\n    RETURN ROW("Scenario", "{c["name"]}", "Metric", "{m}", "Expected", Expected, "Actual", Actual,\n        "Passed", IF(ISBLANK(Expected), ISBLANK(Actual), NOT ISBLANK(Actual) && ABS(Actual - Expected) < 0.000001))'
            )
            expected.append(f"(N'{c['name']}',N'{m}',{number(v)})")
    dax_path = ROOT / "PowerBI/Hospital.SemanticModel/DAXQueries/Acceptance.dax"
    dax_path.parent.mkdir(exist_ok=True)
    dax_path.write_text(
        "// Generated CSV oracle; run in Desktop DAX Query View after refresh.\n// All 374 rows must have Passed = TRUE; BLANK is checked separately from zero.\nEVALUATE\nUNION(\n"
        + ",\n".join(dax)
        + "\n)\nORDER BY [Passed] ASC, [Scenario], [Metric]\n"
    )
    template = (ROOT / "tests/metrics_template.sql").read_text()
    (ROOT / "tests/metrics.sql").write_text(
        template.replace("-- CONTEXT_VALUES", ",\n".join(contexts)).replace(
            "-- EXPECTED_VALUES", ",\n".join(expected)
        )
    )
    print(
        f"Built {len(expected)} metric checks across {len(CONTEXTS)} filter contexts."
    )


if __name__ == "__main__":
    write()
