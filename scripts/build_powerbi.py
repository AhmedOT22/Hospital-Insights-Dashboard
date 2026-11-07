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
    "Billed amount": ("SUM(Billing[TotalAmount])", "#,0.00"),
    "Collected amount": (
        'CALCULATE([Billed amount], KEEPFILTERS(Billing[PaymentStatus] = "Paid"))',
        "#,0.00",
    ),
    "Outstanding amount": (
        'CALCULATE([Billed amount], KEEPFILTERS(Billing[PaymentStatus] = "Unpaid"))',
        "#,0.00",
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
        # Power Query explicitly converts SQL time to datetime as expected by the tabular model.
        expr = [
            "let",
            "    Source = Sql.Database(ServerName, DatabaseName, [CreateNavigationProperties=false]),",
            f'    Rows = Source{{[Schema="dbo", Item="{table}"]}}[Data]',
        ]
        if table == "Appointment":
            expr[-1] += ","
            expr += [
                '    Typed = Table.TransformColumnTypes(Rows, {{"AppointmentTime", type datetime}})',
                "in",
                "    Typed",
            ]
        else:
            expr += ["in", "    Rows"]
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
            ]
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
                    "expression": 'VAR Age = INT(YEARFRAC(Patient[DateOfBirth], DATE(2025,12,31), 1)) RETURN SWITCH(TRUE(), Age < 18, "0–17", Age < 30, "18–29", Age < 50, "30–49", Age < 70, "50–69", "70+")',
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


PAGES = [
    (
        "overview",
        "Executive Overview",
        ["Appointments", "Patients served", "Collected amount", "Outstanding amount"],
        [
            (
                "clusteredColumnChart",
                "Bookings by month (Jan 2026 scheduled)",
                "Appointment",
                "Month",
                ["Appointments"],
            ),
            (
                "clusteredBarChart",
                "Collected amount by service department",
                "Department",
                "DepartmentName",
                ["Collected amount"],
            ),
            (
                "donutChart",
                "Appointment outcomes",
                "Appointment",
                "Status",
                ["Appointments"],
            ),
            (
                "clusteredBarChart",
                "Cancellation rate by service department",
                "Department",
                "DepartmentName",
                ["Cancellation rate"],
            ),
        ],
    ),
    (
        "appointments",
        "Appointments",
        [
            "Completed appointments",
            "Cancelled appointments",
            "Scheduled appointments",
            "Completion rate",
        ],
        [
            (
                "lineChart",
                "Recorded appointments by month",
                "Appointment",
                "Month",
                ["Appointments"],
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
        ["Appointments", "Collection rate", "Rooms", "Snapshot occupancy"],
        [
            (
                "clusteredBarChart",
                "Activity by service department",
                "Department",
                "DepartmentName",
                ["Appointments"],
            ),
            (
                "clusteredColumnChart",
                "Billed and collected by service department",
                "Department",
                "DepartmentName",
                ["Billed amount", "Collected amount"],
            ),
            (
                "clusteredBarChart",
                "Collection rate by service department",
                "Department",
                "DepartmentName",
                ["Collection rate"],
            ),
            (
                "clusteredBarChart",
                "Snapshot occupancy by department",
                "Department",
                "DepartmentName",
                ["Snapshot occupancy"],
            ),
        ],
    ),
    (
        "doctors",
        "Doctors",
        [
            "Doctors with appointments",
            "Completed appointments",
            "Patients served",
            "Cancellation rate",
        ],
        [
            (
                "clusteredBarChart",
                "Completed workload • busiest five doctors",
                "Doctor",
                "Doctor name",
                ["Completed appointments"],
            ),
            (
                "clusteredBarChart",
                "Patients served • busiest five doctors",
                "Doctor",
                "Doctor name",
                ["Patients served"],
            ),
            (
                "clusteredBarChart",
                "Cancellation rate by service department",
                "Department",
                "DepartmentName",
                ["Cancellation rate"],
            ),
            (
                "lineChart",
                "Completed workload over time • select a doctor",
                "Appointment",
                "Month",
                ["Completed appointments"],
            ),
        ],
    ),
    (
        "patients",
        "Patients",
        ["Patients served", "Repeat patients", "Visits", "Prescriptions"],
        [
            (
                "clusteredColumnChart",
                "Patients served by age at snapshot",
                "Patient",
                "Age group at snapshot",
                ["Patients served"],
            ),
            (
                "donutChart",
                "Patients served by recorded gender",
                "Patient",
                "Gender",
                ["Patients served"],
            ),
            (
                "clusteredColumnChart",
                "Completed vs cancelled by age cohort",
                "Patient",
                "Age group at snapshot",
                ["Completed appointments", "Cancelled appointments"],
            ),
            (
                "lineChart",
                "Completed patient activity",
                "Appointment",
                "Month",
                ["Completed appointments"],
            ),
        ],
    ),
]


def visual(page, name, kind, title, x, y, w, h, roles=None, objects=None):
    pos = {
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "z": len(list((REPORT / "definition/pages" / page / "visuals").glob("*"))),
        "tabOrder": len(
            list((REPORT / "definition/pages" / page / "visuals").glob("*"))
        ),
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
                        "fontSize": literal(12),
                        "fontColor": fill("#18394A"),
                        "alignment": literal("left"),
                    }
                }
            ],
            "background": [
                {
                    "properties": {
                        "show": literal(True),
                        "color": fill("#FFFFFF"),
                        "transparency": literal(0),
                    }
                }
            ],
            "border": [{"properties": {"show": literal(False)}}],
            "visualHeader": [{"properties": {"show": literal(False)}}],
        },
    }
    if roles:
        cfg["query"] = {
            "queryState": {
                role: {
                    "projections": [
                        {
                            "field": field(t, n, m),
                            "queryRef": t + "." + n,
                            "nativeQueryRef": n,
                            "displayName": ({"Completed appointments": "Completed", "Cancelled appointments": "Cancelled", "Scheduled appointments": "Scheduled", "Doctors with appointments": "Doctors with bookings", "Outstanding amount": "Outstanding", "Collected amount": "Collected"}.get(n, n) if kind == "cardVisual" else n),
                        }
                        for t, n, m in fields
                    ]
                }
                for role, fields in roles.items()
            }
        }
    if roles and "Category" in roles:
        t, n, m = roles["Category"][0]
        if n == "Month":
            cfg["query"]["sortDefinition"] = {
                "sort": [{"field": field(t, n, m), "direction": "Ascending"}],
                "isDefaultSort": False,
            }
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
        cfg["visualContainerObjects"]["background"] = [
            {"properties": {"show": literal(False)}}
        ]
        cfg["visualContainerObjects"]["visualLink"] = [
            {
                "properties": {
                    "show": literal(True),
                    "type": literal("PageNavigation"),
                    "navigationSection": literal(name.removeprefix("nav_")),
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


def report():
    import shutil

    if (REPORT / "definition").exists():
        shutil.rmtree(REPORT / "definition")
    theme = {
        "name": "Hospital Clinical",
        "dataColors": [
            "#176B87",
            "#1D887D",
            "#64A8B5",
            "#D29A43",
            "#77899C",
            "#A6C8CF",
        ],
        "background": "#F4F7FA",
        "foreground": "#18394A",
        "tableAccent": "#176B87",
        "textClasses": {
            "title": {"fontFace": "Segoe UI", "fontSize": 12, "color": "#18394A"},
            "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": "#496572"},
        },
    }
    save(REPORT / "StaticResources/RegisteredResources/Clinical.json", theme)
    save(
        REPORT / "definition/report.json",
        {
            "$schema": SCHEMA + "definition/report/1.0.0/schema.json",
            "layoutOptimization": "None",
            "themeCollection": {
                "customTheme": {
                    "name": "Clinical",
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
                            "name": "Clinical",
                            "path": "Clinical.json",
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
                                "color": fill("#F4F7FA"),
                                "transparency": literal(0),
                            }
                        }
                    ]
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
                                                    "fontFamily": "Segoe UI",
                                                    "fontSize": f"{size}pt",
                                                    "color": "#18394A",
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

        text("heading", label, 24, 9, 970, 46, 21)
        text(
            "context",
            "Synthetic hospital demonstration • Outcomes through Dec 31, 2025 • Amounts in demo currency units",
            24,
            61,
            1232,
            26,
            10,
        )
        for i, (target, target_label, _, _) in enumerate(PAGES):
            visual(
                page,
                "nav_" + target,
                "actionButton",
                target_label,
                24 + i * 248,
                98,
                236,
                44,
                objects={
                    "text": [
                        {"properties": {"show": literal(True)}},
                        {
                            "properties": {
                                "text": literal(target_label),
                                "fontSize": literal(11),
                                "fontColor": fill(
                                    "#FFFFFF" if target == page else "#18394A"
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
                                    "#176B87" if target == page else "#E5EEF3"
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
        value_size = min(28, max(12, math.floor(720 * 0.028)))
        label_size = min(14, max(8, math.floor(value_size * 0.55)))
        card_height = (
            34 + math.ceil(value_size * 1.5) + math.ceil(max(label_size, 12) * 1.5)
        )
        for i, measure in enumerate(cards):
            visual(
                page,
                f"kpi{i}",
                "cardVisual",
                measure,
                24 + i * 312,
                156,
                296,
                card_height,
                {"Data": [("Appointment", measure, True)]},
                objects={
                    obj: [{"properties": props, "selector": {"id": "default"}}]
                    for obj, props in {
                        "value": {
                            "fontSize": literal(value_size),
                            "fontColor": fill("#176B87"),
                        },
                        "label": {"fontSize": literal(label_size)},
                        "padding": {"paddingUniform": literal(8)},
                        "layout": {"paddingUniform": literal(0)},
                    }.items()
                },
            )
        for i, (kind, title, table, category, measures) in enumerate(charts):
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
                250 + (i // 2) * 184,
                608,
                172,
                roles,
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
            )
        text(
            "footnote",
            "Service and collection rates follow appointment cohorts; room occupancy is a fixed snapshot."
            if page == "departments"
            else "Rates exclude future scheduled outcomes. Financial measures follow visit cohorts, not payment-date cash flow.",
            856,
            632,
            400,
            64,
            9,
        )
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
