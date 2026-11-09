"""Build editable PBIP/PBIR source against the eleven SQL Server tables."""

import json
import math
from pathlib import Path
import re
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "PowerBI"
REPORT = BASE / "Hospital.Report"
MODEL = BASE / "Hospital.SemanticModel"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def literal(v):
    text = (
        ("true" if v else "false")
        if isinstance(v, bool)
        else str(v)
        if isinstance(v, (int, float))
        else "'" + v.replace("'", "''") + "'"
    )
    return {"expr": {"Literal": {"Value": text}}}


def fill(color):
    return {"solid": {"color": literal(color)}}


def field(table, name, measure=False):
    return {
        ("Measure" if measure else "Column"): {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": name,
        }
    }


SNAPSHOT = "DATE(2025, 12, 31)"
AGED_CUTOFF = "DATE(2025, 10, 2)"  # visits more than 90 days before the snapshot

MEASURES = {
    "Appointments": ("COUNTROWS(Appointment)", "#,0"),
    "Completed appointments": (
        'CALCULATE([Appointments], KEEPFILTERS(Appointment[Status] = "Completed"))',
        "#,0",
    ),
    "Cancelled appointments": (
        'CALCULATE([Appointments], KEEPFILTERS(Appointment[Status] = "Cancelled"))',
        "#,0",
    ),
    "Scheduled appointments": (
        'CALCULATE([Appointments], KEEPFILTERS(Appointment[Status] = "Scheduled"))',
        "#,0",
    ),
    "Completion rate": (
        "DIVIDE(COALESCE([Completed appointments], 0), [Completed appointments] + [Cancelled appointments])",
        "0.0%",
    ),
    "Cancellation rate": (
        "DIVIDE(COALESCE([Cancelled appointments], 0), [Completed appointments] + [Cancelled appointments])",
        "0.0%",
    ),
    "Patients served": (
        'CALCULATE(DISTINCTCOUNT(Appointment[PatientID]), KEEPFILTERS(Appointment[Status] = "Completed"))',
        "#,0",
    ),
    "Visits": ("COUNTROWS(Medical_Record)", "#,0"),
    "Prescriptions": ("COUNTROWS(Prescription)", "#,0"),
    "Billed amount": ("SUM(Billing[TotalAmount])", "#,0"),
    "Collected amount": (
        'CALCULATE([Billed amount], KEEPFILTERS(Billing[PaymentStatus] = "Paid"))',
        "#,0",
    ),
    "Outstanding amount": (
        'CALCULATE([Billed amount], KEEPFILTERS(Billing[PaymentStatus] = "Unpaid"))',
        "#,0",
    ),
    "Collection rate": (
        "DIVIDE(COALESCE([Collected amount], 0), [Billed amount])",
        "0.0%",
    ),
    "Doctors with appointments": ("DISTINCTCOUNT(Appointment[DoctorID])", "#,0"),
    "Department doctors": (
        "CALCULATE(COUNTROWS(Doctor), TREATAS(VALUES(Department[DepartmentID]), Doctor[DepartmentID]))",
        "#,0",
    ),
    "Department staff": ("COUNTROWS(Staff)", "#,0"),
    "Rooms": ("COUNTROWS(Room)", "#,0"),
    "Occupied rooms": (
        'CALCULATE([Rooms], KEEPFILTERS(Room[AvailabilityStatus] = "Occupied"))',
        "#,0",
    ),
    "Snapshot occupancy": ("DIVIDE(COALESCE([Occupied rooms], 0), [Rooms])", "0.0%"),
    "Completed stays": (
        "COUNTROWS(FILTER(Room_Assignment, NOT ISBLANK(Room_Assignment[DischargeDate])))",
        "#,0",
    ),
    "Average completed stay": (
        "AVERAGEX(FILTER(Room_Assignment, NOT ISBLANK(Room_Assignment[DischargeDate])), DATEDIFF(Room_Assignment[AdmissionDate], Room_Assignment[DischargeDate], DAY))",
        "0.0",
    ),
    "Repeat patients": (
        "COUNTROWS(FILTER(VALUES(Appointment[PatientID]), CALCULATE([Completed appointments]) > 1))",
        "#,0",
    ),
    # Context measures behind the KPI card notes and highlight colors. They are
    # numeric so the CSV/SQL/DAX acceptance checks cover them like every other KPI.
    "Completed YoY change": (
        "VAR CurrentYear = CALCULATE([Completed appointments], KEEPFILTERS(YEAR(Appointment[AppointmentDate]) = 2025)) "
        "VAR PriorYear = CALCULATE([Completed appointments], KEEPFILTERS(YEAR(Appointment[AppointmentDate]) = 2024)) "
        "RETURN DIVIDE(CurrentYear - PriorYear, PriorYear)",
        "+0.0%;-0.0%;0.0%",
    ),
    "Outstanding over 90 days": (
        f"CALCULATE([Outstanding amount], KEEPFILTERS(Appointment[AppointmentDate] < {AGED_CUTOFF}))",
        "#,0",
    ),
    "Outstanding over 90 days share": (
        "DIVIDE(COALESCE([Outstanding over 90 days], 0), [Outstanding amount])",
        "0.0%",
    ),
    "Average bill per visit": ("DIVIDE([Billed amount], [Visits])", "#,0"),
    "Visits per patient": (
        "DIVIDE([Completed appointments], [Patients served])",
        "0.0",
    ),
    "Highest doctor workload": (
        "MAXX(VALUES(Appointment[DoctorID]), [Completed appointments])",
        "#,0",
    ),
    "Lowest doctor workload": (
        "MINX(VALUES(Appointment[DoctorID]), [Completed appointments])",
        "#,0",
    ),
    "Average completed per doctor": (
        "CALCULATE(DIVIDE([Completed appointments], [Doctors with appointments]), REMOVEFILTERS(Doctor))",
        "#,0.0",
    ),
    "Highest doctor cancellation rate": (
        "MAXX(VALUES(Appointment[DoctorID]), [Cancellation rate])",
        "0.0%",
    ),
    "Cancellation rate all doctors": (
        "CALCULATE([Cancellation rate], REMOVEFILTERS(Doctor))",
        "0.0%",
    ),
}

# "Ward" theme: calm clinical neutrals, deep teal primary, burnt orange reserved for
# what needs attention. Every color used for marks or text keeps >= 3:1 on white.
PRIMARY = "#00737E"  # deep teal: first series, KPI values, current page button
ATTENTION = "#C2410C"  # burnt orange: headline value, above-average bars, nothing else
MUTED = "#7A8B91"  # slate: bars at or below average; 3.5:1 on white
INK = "#14262C"  # titles, headings, values
INK_2 = "#4F6168"  # labels, subtitles, card notes, footnotes
GRID = "#D5DFDC"  # gridlines and axis lines
SOFT = "#E3ECEA"  # nav buttons, borders, applied filter cards
PAGE_BG = "#F3F6F5"  # canvas
WALLPAPER = "#E9EEEC"  # area around the canvas
CARD = "#FFFFFF"  # visual background
# Chart series. The first four pass the categorical color-vision checks together;
# no chart uses more than two series, so 5-8 are fallbacks (all >= 3:1 on white).
DATA_COLORS = [
    PRIMARY,
    "#5A55C2",  # violet
    "#C0457A",  # plum
    "#8F6E00",  # ochre
    "#2F6F8F",
    "#8C5A3C",
    "#4F6168",
    "#6A7F3B",
]


def theme_json():
    def solid(color):
        return {"solid": {"color": color}}

    return {
        "name": "Ward",
        "dataColors": DATA_COLORS,
        "firstLevelElements": INK,
        "secondLevelElements": INK_2,
        "thirdLevelElements": GRID,
        "fourthLevelElements": "#9AA9AE",
        "background": CARD,
        "secondaryBackground": SOFT,
        "tableAccent": PRIMARY,
        "good": "#1F7A4D",
        "neutral": "#8F6E00",
        "bad": "#B42318",
        "maximum": ATTENTION,
        "center": PAGE_BG,
        "minimum": PRIMARY,
        "hyperlink": PRIMARY,
        "visitedHyperlink": "#5A55C2",
        "textClasses": {
            "callout": {"fontFace": "DIN", "fontSize": 18, "color": PRIMARY},
            "title": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": INK},
            "header": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": INK},
            "label": {"fontFace": "Segoe UI", "fontSize": 9, "color": INK_2},
        },
        "visualStyles": {
            "*": {
                "*": {
                    "background": [
                        {"show": True, "color": solid(CARD), "transparency": 0}
                    ],
                    "border": [{"show": True, "color": solid(SOFT), "radius": 8}],
                    "visualTooltip": [
                        {
                            "titleFontColor": INK_2,
                            "valueFontColor": INK,
                            "background": solid(CARD),
                        }
                    ],
                    "outspacePane": [
                        {
                            "backgroundColor": solid(CARD),
                            "foregroundColor": solid(INK),
                            "borderColor": solid(SOFT),
                        }
                    ],
                    "filterCard": [
                        {
                            "$id": "Applied",
                            "backgroundColor": solid(SOFT),
                            "foregroundColor": solid(INK),
                        },
                        {
                            "$id": "Available",
                            "backgroundColor": solid(PAGE_BG),
                            "foregroundColor": solid(INK),
                        },
                    ],
                }
            },
            "page": {
                "*": {
                    "background": [{"color": solid(PAGE_BG), "transparency": 0}],
                    "outspace": [{"color": solid(WALLPAPER), "transparency": 0}],
                }
            },
        },
    }


def note(measure, template):
    """Text for a KPI card's context line; BLANK-safe so cards never read ' of billed'."""
    return f'IF(ISBLANK([{measure}]), "No data for this selection", {template})'


# Text measures shown under KPI values. Built only from oracle-checked measures.
NOTES = {
    "Appointments note": 'FORMAT(COALESCE([Scheduled appointments], 0), "#,0") & " future bookings included"',
    "Patients served note": note(
        "Visits per patient",
        'FORMAT([Visits per patient], "0.0") & " completed visits per patient"',
    ),
    "Collected note": note(
        "Collection rate", 'FORMAT([Collection rate], "0%") & " of billed amount"'
    ),
    "Outstanding note": note(
        "Outstanding over 90 days share",
        'FORMAT([Outstanding over 90 days share], "0%") & " is over 90 days old"',
    ),
    "Completed note": 'IF(ISBLANK([Completed YoY change]), "Select both 2024 and 2025 months to compare years", FORMAT([Completed YoY change], "+0.0%;-0.0%;0.0%") & " in 2025 vs 2024")',
    "Cancelled note": note(
        "Highest doctor cancellation rate",
        '"Highest doctor rate " & FORMAT([Highest doctor cancellation rate], "0.0%")',
    ),
    "Scheduled note": '"Booked after the Dec 31, 2025 snapshot"',
    "Completion rate note": '"Future bookings excluded"',
    "Doctors note": note(
        "Highest doctor workload",
        'FORMAT([Lowest doctor workload], "#,0") & "–" & FORMAT([Highest doctor workload], "#,0") & " completed per doctor"',
    ),
    "Cancellation rate note": note(
        "Highest doctor cancellation rate",
        '"Highest doctor " & FORMAT([Highest doctor cancellation rate], "0.0%")',
    ),
    "Billed note": note(
        "Average bill per visit",
        'FORMAT([Average bill per visit], "#,0") & " per visit on average"',
    ),
    "Collection rate note": note(
        "Outstanding amount", 'FORMAT([Outstanding amount], "#,0") & " still unpaid"'
    ),
    "Completed stays note": note(
        "Average completed stay",
        '"Average stay " & FORMAT([Average completed stay], "0.0") & " days"',
    ),
}

# Field-value colors: orange marks the doctors above the hospital-wide average.
COLORS = {
    "Doctor workload color": f'IF([Completed appointments] > [Average completed per doctor], "{ATTENTION}", "{MUTED}")',
    "Doctor cancellation color": f'IF([Cancellation rate] > [Cancellation rate all doctors], "{ATTENTION}", "{MUTED}")',
}

# Each fact has one active path from a given dimension. Extra operational foreign
# keys remain inactive; no bidirectional relationships or preaggregated totals.
RELATIONS = [
    ("Appointment", "DepartmentID", "Department", "DepartmentID", True),
    ("Doctor", "DepartmentID", "Department", "DepartmentID", False),
    ("Room", "DepartmentID", "Department", "DepartmentID", True),
    ("Staff", "DepartmentID", "Department", "DepartmentID", True),
    ("Appointment", "DoctorID", "Doctor", "DoctorID", True),
    ("Appointment", "PatientID", "Patient", "PatientID", True),
    ("Medical_Record", "AppointmentID", "Appointment", "AppointmentID", True),
    ("Medical_Record", "PatientID", "Patient", "PatientID", False),
    ("Medical_Record", "DoctorID", "Doctor", "DoctorID", False),
    ("Prescription", "RecordID", "Medical_Record", "RecordID", True),
    ("Prescription", "MedicineID", "Medicine", "MedicineID", True),
    ("Billing", "RecordID", "Medical_Record", "RecordID", True),
    ("Billing", "PatientID", "Patient", "PatientID", False),
    ("Room_Assignment", "PatientID", "Patient", "PatientID", True),
    ("Room_Assignment", "RoomID", "Room", "RoomID", True),
]


def semantic_model():
    sql = (ROOT / "sql/model.sql").read_text()
    tables = []
    for table, body in re.findall(
        r"CREATE TABLE dbo\.(\w+)\s*\((.*?)\n    \);", sql, re.S
    ):
        columns = []
        for name, kind in re.findall(
            r"^\s*(\w+)\s+(INT|N?VARCHAR|DECIMAL|DATE|TIME|BIT)\b", body, re.M
        ):
            dtype = {
                "INT": "int64",
                "DECIMAL": "decimal",
                "DATE": "dateTime",
                "TIME": "dateTime",
                "BIT": "boolean",
            }.get(kind, "string")
            col = {
                "name": name,
                "dataType": dtype,
                "sourceColumn": name,
                "summarizeBy": "none",
            }
            if name.endswith("ID"):
                col["isHidden"] = True
            if kind == "DATE":
                col["formatString"] = "yyyy-MM-dd"
            if kind == "TIME":
                col["formatString"] = "HH:mm"
            columns.append(col)
        # Every table loads with the same two-step query. SQL time columns arrive as
        # M time values and the model stores them as dateTime by itself; an extra
        # Table.TransformColumnTypes step on Appointment made Desktop refresh fail
        # with "A cyclic reference was encountered during evaluation".
        expr = [
            "let",
            "    Source = Sql.Database(ServerName, DatabaseName, [CreateNavigationProperties=false]),",
            f'    Rows = Source{{[Schema="dbo", Item="{table}"]}}[Data]',
            "in",
            "    Rows",
        ]
        t = {
            "name": table,
            "columns": columns,
            "partitions": [
                {
                    "name": table,
                    "mode": "import",
                    "source": {"type": "m", "expression": expr},
                }
            ],
        }
        if table == "Appointment":
            t["columns"].append(
                {
                    "name": "Month",
                    "dataType": "string",
                    "type": "calculated",
                    "expression": 'FORMAT(Appointment[AppointmentDate], "yyyy-MM")',
                    "summarizeBy": "none",
                }
            )
            t["measures"] = [
                {
                    "name": n,
                    "expression": e,
                    "formatString": fmt,
                    "displayFolder": "Hospital KPIs",
                }
                for n, (e, fmt) in MEASURES.items()
            ] + [
                {"name": n, "expression": e, "displayFolder": folder}
                for folder, group in (("Card notes", NOTES), ("Highlight colors", COLORS))
                for n, e in group.items()
            ]
        if table == "Billing":
            # Age of the linked visit at the snapshot; drives the receivables aging chart.
            # Labels sort correctly as text: 0–30, 31–90, 91–365, Over 365.
            t["columns"].append(
                {
                    "name": "Visit age band",
                    "dataType": "string",
                    "type": "calculated",
                    "expression": f"VAR Age = INT({SNAPSHOT} - RELATED(Appointment[AppointmentDate])) "
                    'RETURN SWITCH(TRUE(), Age <= 30, "0–30 days", Age <= 90, "31–90 days", '
                    'Age <= 365, "91–365 days", "Over 365 days")',
                    "summarizeBy": "none",
                }
            )
        if table == "Doctor":
            t["columns"].append(
                {
                    "name": "Doctor name",
                    "dataType": "string",
                    "type": "calculated",
                    "expression": 'Doctor[FirstName] & " " & Doctor[LastName]',
                    "summarizeBy": "none",
                }
            )
        if table == "Patient":
            t["columns"].append(
                {
                    "name": "Age group at snapshot",
                    "dataType": "string",
                    "type": "calculated",
                    "expression": 'VAR Age = INT(YEARFRAC(Patient[DateOfBirth], ' + SNAPSHOT + ', 1)) RETURN SWITCH(TRUE(), Age < 18, "0–17", Age < 30, "18–29", Age < 50, "30–49", Age < 70, "50–69", "70+")',
                    "summarizeBy": "none",
                }
            )
        tables.append(t)
    relationships = [
        {
            "name": str(uuid.uuid5(uuid.NAMESPACE_URL, "/".join([a, b, c, d]))),
            "fromTable": a,
            "fromColumn": b,
            "fromCardinality": "many",
            "toTable": c,
            "toColumn": d,
            "toCardinality": "one",
            "crossFilteringBehavior": "oneDirection",
            "isActive": active,
        }
        for a, b, c, d, active in RELATIONS
    ]
    model = {
        "name": "Hospital",
        "compatibilityLevel": 1601,
        "model": {
            "culture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "discourageImplicitMeasures": True,
            "tables": tables,
            "relationships": relationships,
            "expressions": [
                {
                    "name": "ServerName",
                    "kind": "m",
                    "expression": '"localhost" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                },
                {
                    "name": "DatabaseName",
                    "kind": "m",
                    "expression": '"HospitalInsights" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                },
            ],
        },
    }
    save(MODEL / "model.bim", model)
    save(MODEL / "definition.pbism", {"version": "1.0", "settings": {}})


# Each page is (id, title, KPI cards, charts). A card is (measure, note measure or
# None); the note is a context line under the value ("84% of billed amount"). Each
# chart is (visual type, title, category table, category column, measures). Pages
# with two charts give each one the full chart-area height, so 20 doctors fit
# without scrolling; with three, the last chart spans the bottom row. No
# category/measure pair repeats, and every chart shows real variation in the
# generated data; flat comparisons (gender, weekday, department collection rate,
# room occupancy, repeat patients) are deliberately left out.
PAGES = [
    (
        "overview",
        "Executive Overview",
        [
            ("Appointments", "Appointments note"),
            ("Patients served", "Patients served note"),
            ("Collected amount", "Collected note"),
            ("Outstanding amount", "Outstanding note"),
        ],
        [
            (
                "clusteredColumnChart",
                "Unpaid amount by age of visit",
                "Billing",
                "Visit age band",
                ["Outstanding amount"],
            ),
            (
                "barChart",
                "Collected and unpaid by service department",
                "Department",
                "DepartmentName",
                ["Collected amount", "Outstanding amount"],
            ),
            (
                "clusteredColumnChart",
                "Patients served by month",
                "Appointment",
                "Month",
                ["Patients served"],
            ),
        ],
    ),
    (
        "appointments",
        "Appointments",
        [
            ("Completed appointments", "Completed note"),
            ("Cancelled appointments", "Cancelled note"),
            ("Scheduled appointments", "Scheduled note"),
            ("Completion rate", "Completion rate note"),
        ],
        [
            (
                "lineChart",
                "Completed and cancelled by month",
                "Appointment",
                "Month",
                ["Completed appointments", "Cancelled appointments"],
            ),
            (
                "clusteredColumnChart",
                "Outcomes by service department",
                "Department",
                "DepartmentName",
                ["Completed appointments", "Cancelled appointments"],
            ),
            (
                "lineChart",
                "Cancellation rate by month",
                "Appointment",
                "Month",
                ["Cancellation rate"],
            ),
            (
                "clusteredBarChart",
                "Future scheduled bookings by department",
                "Department",
                "DepartmentName",
                ["Scheduled appointments"],
            ),
        ],
    ),
    (
        "departments",
        "Departments",
        [
            ("Appointments", "Appointments note"),
            ("Billed amount", "Billed note"),
            ("Collection rate", "Collection rate note"),
            ("Completed stays", "Completed stays note"),
        ],
        [
            (
                "clusteredBarChart",
                "Activity by service department",
                "Department",
                "DepartmentName",
                ["Appointments"],
            ),
            (
                "clusteredBarChart",
                "Average bill per visit by department",
                "Department",
                "DepartmentName",
                ["Average bill per visit"],
            ),
            (
                "clusteredBarChart",
                "Unpaid over 90 days by department",
                "Department",
                "DepartmentName",
                ["Outstanding over 90 days"],
            ),
            (
                "clusteredBarChart",
                "Completed room stays by department",
                "Department",
                "DepartmentName",
                ["Completed stays"],
            ),
        ],
    ),
    (
        "doctors",
        "Doctors",
        [
            ("Doctors with appointments", "Doctors note"),
            ("Completed appointments", "Completed note"),
            ("Patients served", "Patients served note"),
            ("Cancellation rate", "Cancellation rate note"),
        ],
        [
            (
                "clusteredBarChart",
                "Completed appointments by doctor • orange = above average",
                "Doctor",
                "Doctor name",
                ["Completed appointments"],
            ),
            (
                "clusteredBarChart",
                "Cancellation rate by doctor • orange = above average",
                "Doctor",
                "Doctor name",
                ["Cancellation rate"],
            ),
        ],
    ),
    (
        "patients",
        "Patients",
        [
            ("Patients served", "Patients served note"),
            ("Visits", None),
            ("Prescriptions", None),
            ("Cancellation rate", "Cancellation rate note"),
        ],
        [
            (
                "clusteredColumnChart",
                "Patients served by age at snapshot",
                "Patient",
                "Age group at snapshot",
                ["Patients served"],
            ),
            (
                "clusteredColumnChart",
                "Completed vs cancelled by age at snapshot",
                "Patient",
                "Age group at snapshot",
                ["Completed appointments", "Cancelled appointments"],
            ),
            (
                "lineChart",
                "Prescriptions by visit month",
                "Appointment",
                "Month",
                ["Prescriptions"],
            ),
        ],
    ),
]

# One headline card per page, drawn in orange: the number that needs attention.
HEADLINES = {
    "overview": "Outstanding amount",
    "appointments": "Cancelled appointments",
    "doctors": "Cancellation rate",
    "patients": "Cancellation rate",
}
# Bars colored per data point from a field-value color measure.
CHART_COLORS = {
    "Completed appointments by doctor • orange = above average": "Doctor workload color",
    "Cancellation rate by doctor • orange = above average": "Doctor cancellation color",
}
# Categories shown in natural order instead of sorted by value.
NATURAL_ORDER = ("Month", "Age group at snapshot", "Visit age band")


CARD_LABELS = {
    "Completed appointments": "Completed",
    "Cancelled appointments": "Cancelled",
    "Scheduled appointments": "Scheduled",
    "Doctors with appointments": "Doctors with bookings",
    "Outstanding amount": "Outstanding",
    "Collected amount": "Collected",
}
CHART_NAMES = {
    "clusteredBarChart": "Bar chart",
    "clusteredColumnChart": "Column chart",
    "lineChart": "Line chart",
    "barChart": "Stacked bar chart",
    "donutChart": "Donut chart",
}


def assign_tab_order(page):
    """Power BI focuses the highest tabOrder first. Visuals are created in
    reading order (top to bottom, left to right; z records that order), so the
    first visual gets N * 1000 and the last gets 1000."""
    paths = list((REPORT / "definition/pages" / page / "visuals").glob("*/visual.json"))
    docs = sorted(
        ((path, json.loads(path.read_text())) for path in paths),
        key=lambda item: item[1]["position"]["z"],
    )
    for rank, (path, doc) in enumerate(docs):
        doc["position"]["tabOrder"] = (len(docs) - rank) * 1000
        save(path, doc)


def visual(page, name, kind, title, x, y, w, h, roles=None, objects=None, alt=None):
    index = len(list((REPORT / "definition/pages" / page / "visuals").glob("*")))
    pos = {
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "z": index,
        "tabOrder": 0,  # final value set by assign_tab_order()
    }
    cfg = {
        "visualType": kind,
        "visualContainerObjects": {
            "title": [
                {
                    "properties": {
                        "show": literal(
                            kind
                            not in ("textbox", "actionButton", "cardVisual", "slicer")
                        ),
                        "text": literal(title),
                        "fontSize": literal(11),
                        "fontColor": fill(INK),
                        "alignment": literal("left"),
                    }
                }
            ],
            # Text sits directly on the canvas; cards, charts and slicers are white
            # panels, and charts and slicers also get a hairline rounded border.
            "background": [
                {
                    "properties": {
                        "show": literal(kind != "textbox"),
                        "color": fill(CARD),
                        "transparency": literal(0),
                    }
                }
            ],
            "border": [
                {
                    "properties": {
                        "show": literal(kind not in ("textbox", "actionButton", "cardVisual")),
                        "color": fill(SOFT),
                        "radius": literal(8),
                    }
                }
            ],
            "visualHeader": [{"properties": {"show": literal(False)}}],
        },
    }
    if alt:
        # Screen readers announce altText; keep it short and describe the content.
        cfg["visualContainerObjects"]["general"] = [
            {"properties": {"altText": literal(alt)}}
        ]
    if roles:
        cfg["query"] = {
            "queryState": {
                role: {
                    "projections": [
                        {
                            "field": field(t, n, m),
                            "queryRef": t + "." + n,
                            "nativeQueryRef": n,
                            "displayName": (
                                CARD_LABELS.get(n, n) if kind == "cardVisual" else n
                            ),
                        }
                        for t, n, m in fields
                    ]
                }
                for role, fields in roles.items()
            }
        }
    if roles and "Category" in roles:
        t, n, m = roles["Category"][0]
        if n in NATURAL_ORDER:
            cfg["query"]["sortDefinition"] = {
                "sort": [{"field": field(t, n, m), "direction": "Ascending"}],
                "isDefaultSort": False,
            }
    if kind == "textbox":
        cfg["visualContainerObjects"]["padding"] = [
            {"properties": {side: literal(0) for side in ("top", "bottom", "left", "right")}}
        ]
    if kind == "slicer":
        cfg["visualContainerObjects"]["padding"] = [
            {
                "properties": {
                    side: literal(8) for side in ("top", "bottom", "left", "right")
                }
            }
        ]
        cfg["objects"] = {
            "data": [{"properties": {"mode": literal("Dropdown")}}],
            "header": [
                {
                    "properties": {
                        "show": literal(True),
                        "text": literal(title),
                        "textSize": literal(10),
                    }
                }
            ],
            "items": [{"properties": {"textSize": literal(10)}}],
        }
    if kind == "cardVisual":
        cfg["visualContainerObjects"]["padding"] = [
            {
                "properties": {
                    side: literal(8) for side in ("top", "bottom", "left", "right")
                },
                "selector": {"id": "default"},
            }
        ]
        cfg["visualContainerObjects"]["spacing"] = [
            {
                "properties": {
                    "customizeSpacing": literal(True),
                    "verticalSpacing": literal(2),
                },
                "selector": {"id": "default"},
            }
        ]
    if kind == "actionButton":
        target = name.removeprefix("nav_")
        cfg["visualContainerObjects"]["background"] = [
            {"properties": {"show": literal(False)}}
        ]
        cfg["visualContainerObjects"]["visualLink"] = [
            {
                "properties": {
                    "show": literal(True),
                    "type": literal("PageNavigation"),
                    "navigationSection": literal(target),
                    "tooltip": literal(
                        f"{title} (current page)"
                        if target == page
                        else f"Go to the {title} page"
                    ),
                }
            }
        ]
    if objects:
        cfg["objects"] = objects
    save(
        REPORT / "definition/pages" / page / "visuals" / name / "visual.json",
        {
            "$schema": SCHEMA + "definition/visualContainer/2.9.0/schema.json",
            "name": name,
            "position": pos,
            "visual": cfg,
        },
    )


def card_objects(value, label, padding=8):
    return {
        obj: [{"properties": props, "selector": {"id": "default"}}]
        for obj, props in {
            "value": value,
            "label": label,
            "padding": {"paddingUniform": literal(padding)},
            "layout": {"paddingUniform": literal(0)},
        }.items()
    }


def chart_objects(kind, category, color_measure=None):
    """Value labels replace the value axis on category charts (months keep the
    axis: 25 labels would collide). A color measure colors each data point."""
    objects = {}
    if kind != "lineChart" and category != "Month":
        objects["labels"] = [{"properties": {"show": literal(True)}}]
        objects["valueAxis"] = [
            {
                "properties": {
                    "show": literal(False),
                    "gridlineShow": literal(False),
                }
            }
        ]
    if color_measure:
        objects["dataPoint"] = [
            {
                "properties": {
                    "fill": {
                        "solid": {
                            "color": {
                                "expr": field("Appointment", color_measure, True)
                            }
                        }
                    }
                },
                "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]},
            }
        ]
    return objects or None


def report():
    import shutil

    if (REPORT / "definition").exists():
        shutil.rmtree(REPORT / "definition")
    resources = REPORT / "StaticResources/RegisteredResources"
    (resources / "Clinical.json").unlink(missing_ok=True)  # previous theme
    save(resources / "Ward.json", theme_json())
    save(
        REPORT / "definition/report.json",
        {
            "$schema": SCHEMA + "definition/report/1.0.0/schema.json",
            "layoutOptimization": "None",
            "themeCollection": {
                "customTheme": {
                    "name": "Ward",
                    "reportVersionAtImport": "5.59",
                    "type": "RegisteredResources",
                }
            },
            "resourcePackages": [
                {
                    "name": "RegisteredResources",
                    "type": "RegisteredResources",
                    "items": [
                        {
                            "name": "Ward",
                            "path": "Ward.json",
                            "type": "CustomTheme",
                        }
                    ],
                }
            ],
        },
    )
    save(
        REPORT / "definition/version.json",
        {"$schema": SCHEMA + "definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"},
    )
    save(
        REPORT / "definition/pages/pages.json",
        {
            "$schema": SCHEMA + "definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [p[0] for p in PAGES],
            "activePageName": "overview",
        },
    )
    for page, label, cards, charts in PAGES:
        save(
            REPORT / "definition/pages" / page / "page.json",
            {
                "$schema": SCHEMA + "definition/page/1.0.0/schema.json",
                "name": page,
                "displayName": label,
                "displayOption": "FitToPage",
                "width": 1280,
                "height": 720,
                "objects": {
                    "background": [
                        {
                            "properties": {
                                "color": fill(PAGE_BG),
                                "transparency": literal(0),
                            }
                        }
                    ],
                    "outspace": [
                        {
                            "properties": {
                                "color": fill(WALLPAPER),
                                "transparency": literal(0),
                            }
                        }
                    ],
                },
            },
        )

        # Text is rendered through the native Power BI textbox visual.
        def text(name, value, x, y, w, h, size=12):
            visual(
                page,
                name,
                "textbox",
                "",
                x,
                y,
                w,
                h,
                alt=value,
                objects={
                    "general": [
                        {
                            "properties": {
                                "paragraphs": [
                                    {
                                        "textRuns": [
                                            {
                                                "value": value,
                                                "textStyle": {
                                                    "fontFamily": "Segoe UI Semibold"
                                                    if size > 12
                                                    else "Segoe UI",
                                                    "fontSize": f"{size}pt",
                                                    "color": INK if size > 12 else INK_2,
                                                },
                                            }
                                        ]
                                    }
                                ]
                            }
                        }
                    ]
                },
            )

        # Boxes leave room for a full line at each size (21 pt needs ~38 px, 10 pt
        # ~18 px); with Desktop's default padding they clipped and showed scrollbars.
        text("heading", label, 24, 2, 970, 52, 21)
        text(
            "context",
            "Synthetic hospital demonstration • Outcomes through Dec 31, 2025 • Amounts in demo currency units",
            24,
            54,
            1232,
            32,
            10,
        )
        for i, (target, target_label, _, _) in enumerate(PAGES):
            visual(
                page,
                "nav_" + target,
                "actionButton",
                target_label,
                24 + i * 248,
                89,
                236,
                44,
                alt=f"{target_label} page button.",
                objects={
                    "text": [
                        {"properties": {"show": literal(True)}},
                        {
                            "properties": {
                                "text": literal(target_label),
                                "fontSize": literal(11),
                                "fontColor": fill(
                                    "#FFFFFF" if target == page else INK
                                ),
                                "horizontalAlignment": literal("center"),
                            },
                            "selector": {"id": "default"},
                        },
                    ],
                    "icon": [
                        {"properties": {"show": literal(False)}},
                        {
                            "properties": {"placement": literal("left")},
                            "selector": {"id": "default"},
                        },
                    ],
                    "fill": [
                        {"properties": {"show": literal(True)}},
                        {
                            "properties": {
                                "fillColor": fill(
                                    PRIMARY if target == page else SOFT
                                )
                            },
                            "selector": {"id": "default"},
                        },
                    ],
                    "outline": [{"properties": {"show": literal(False)}}],
                    "shape": [
                        {
                            "properties": {
                                "tileShape": literal("rectangleRounded"),
                                "roundEdge": literal(6),
                            }
                        },
                        {
                            "properties": {"tileShape": literal("rectangleRounded")},
                            "selector": {"id": "default"},
                        },
                    ],
                },
            )
        value_size = 18  # matches the theme's callout text class
        label_size = min(14, max(8, math.floor(value_size * 0.55)))
        for i, (measure, note_measure) in enumerate(cards):
            label = CARD_LABELS.get(measure, measure)
            highlight = HEADLINES.get(page) == measure
            visual(
                page,
                f"kpi{i}",
                "cardVisual",
                measure,
                24 + i * 312,
                144,
                296,
                68,
                {"Data": [("Appointment", measure, True)]},
                alt=f"KPI card showing {label.lower()} for the current selection"
                + (", highlighted as this page's headline." if highlight else "."),
                objects=card_objects(
                    {
                        "fontSize": literal(value_size),
                        "fontColor": fill(ATTENTION if highlight else PRIMARY),
                    },
                    {"fontSize": literal(label_size)},
                ),
            )
        # Context lines sit in a second row so reading order stays top to bottom.
        for i, (measure, note_measure) in enumerate(cards):
            if not note_measure:
                continue
            label = CARD_LABELS.get(measure, measure)
            visual(
                page,
                f"kpi{i}_note",
                "cardVisual",
                note_measure,
                24 + i * 312,
                212,
                296,
                32,
                {"Data": [("Appointment", note_measure, True)]},
                alt=f"Context for {label.lower()}, such as share, comparison or average.",
                objects=card_objects(
                    {"fontSize": literal(9), "fontColor": fill(INK_2)},
                    {"show": literal(False)},
                    padding=4,
                ),
            )
        tall = len(charts) == 2
        for i, (kind, title, table, category, measures) in enumerate(charts):
            # With three charts the last one spans the full width of the bottom row.
            wide = len(charts) == 3 and i == 2
            roles = {
                "Category": [(table, category, False)],
                "Y": [("Appointment", m, True) for m in measures],
            }
            visual(
                page,
                f"chart{i}",
                kind,
                title,
                24 + (i % 2) * 624,
                250 + (0 if tall else (i // 2) * 184),
                1232 if wide else 608,
                356 if tall else 172,
                roles,
                alt=f"{CHART_NAMES[kind]}: {title.split(' • ')[0]}.",
                objects=chart_objects(kind, category, CHART_COLORS.get(title)),
            )
        visual(
            page,
            "department_filter",
            "slicer",
            "Service department",
            24,
            624,
            400,
            80,
            {"Values": [("Department", "DepartmentName", False)]},
            alt="Dropdown filter to select a service department.",
        )
        if page in ("overview", "appointments", "patients"):
            visual(
                page,
                "month_filter",
                "slicer",
                "Appointment month",
                440,
                624,
                400,
                80,
                {"Values": [("Appointment", "Month", False)]},
                alt="Dropdown filter to select an appointment month.",
            )
        if page == "doctors":
            visual(
                page,
                "doctor_filter",
                "slicer",
                "Select doctor",
                440,
                624,
                400,
                80,
                {"Values": [("Doctor", "Doctor name", False)]},
                alt="Dropdown filter to select a doctor.",
            )
        text(
            "footnote",
            "Room stays follow the room's department; amounts and prescriptions follow appointment cohorts."
            if page == "departments"
            else "Completed and cancelled outcomes run to Dec 31, 2025; Jan 2026 holds future bookings only. Amounts follow visit month, not payment date.",
            856,
            632,
            400,
            64,
            9,
        )
        assign_tab_order(page)
    save(
        REPORT / "definition.pbir",
        {
            "$schema": SCHEMA + "definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../Hospital.SemanticModel"}},
        },
    )
    save(
        BASE / "Hospital.pbip",
        {
            "version": "1.0",
            "artifacts": [{"report": {"path": "Hospital.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )


if __name__ == "__main__":
    semantic_model()
    report()
    print("Built eleven-table semantic model and five-page PBIR report.")
