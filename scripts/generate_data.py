"""Build deterministic, linked demonstration records; no real patient information."""

import csv
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2025, 12, 31)
SEED = 42


def generate():
    rng = random.Random(SEED)
    tables = {
        n: []
        for n in (
            "Department",
            "Medicine",
            "Patient",
            "Staff",
            "Doctor",
            "Room",
            "Appointment",
            "Medical_Record",
            "Prescription",
            "Billing",
            "Room_Assignment",
        )
    }

    def add(table, **row):
        tables[table].append(row)
        return row

    departments = ["Cardiology", "Pediatrics", "Emergency", "Orthopedics", "Neurology"]
    for i, name in enumerate(departments, 1):
        add(
            "Department",
            DepartmentID=i,
            DepartmentName=name,
            Location=f"Wing {i}",
            PhoneExtension=str(1000 + i),
            IsActive=1,
        )
    for i in range(1, 51):
        add(
            "Medicine",
            MedicineID=i,
            MedicineName=f"Demo medicine {i:02}",
            Manufacturer="Synthetic supplier",
            StockQuantity=rng.randrange(20, 400),
            Price=round(rng.uniform(5, 90), 2),
        )
    for i in range(1, 201):
        birth_year = rng.randrange(2011, 2023) if i <= 50 else rng.randrange(1940, 2005)
        add(
            "Patient",
            PatientID=i,
            FirstName=f"Patient {i:03}",
            LastName="Demo",
            DateOfBirth=date(
                birth_year, rng.randrange(1, 13), rng.randrange(1, 28)
            ).isoformat(),
            Gender=rng.choice(["Female", "Male"]),
            Address="Synthetic address",
            PhoneNumber=None,
            Email=None,
            EmergencyContactName=None,
            EmergencyContactPhone=None,
            IsActive=1,
        )
    for i in range(1, 21):
        dept = (i - 1) // 4 + 1
        add(
            "Doctor",
            DoctorID=i,
            FirstName=f"Doctor {i:02}",
            LastName="Demo",
            Specialization=departments[dept - 1],
            PhoneNumber=None,
            Email=None,
            DepartmentID=dept,
            Availability=1,
            IsActive=1,
        )
    for i in range(1, 51):
        add(
            "Staff",
            StaffID=i,
            FirstName=f"Staff {i:02}",
            LastName="Demo",
            Role=rng.choice(["Nurse", "Administrator", "Technician"]),
            DepartmentID=(i - 1) % 5 + 1,
            PhoneNumber=None,
            Email=None,
            ShiftHours="08:00-16:00",
            IsActive=1,
        )
    for i in range(1, 21):
        add(
            "Room",
            RoomID=i,
            RoomNumber=str(100 + i),
            DepartmentID=(i - 1) // 4 + 1,
            RoomType="Private",
            AvailabilityStatus="Available",
        )
    # One-person rooms in this demo. Each assignment advances its room's free date.
    room_free = {i: date(2024, 1, 1) for i in range(1, 21)}
    patient_free = {i: date(2024, 1, 1) for i in range(1, 201)}
    used_doctor = set()
    used_patient = set()
    for day_offset in range(741):
        day = date(2024, 1, 1) + timedelta(days=day_offset)
        for _ in range(rng.randrange(3, 10)):
            dept = rng.choices(range(1, 6), weights=[4, 3, 7, 4, 2])[0]
            doctor = (dept - 1) * 4 + rng.randrange(1, 5)
            patient = rng.randrange(1, 51) if dept == 2 else rng.randrange(51, 201)
            hour = rng.randrange(8, 17)
            if (doctor, day, hour) in used_doctor or (
                patient,
                day,
                hour,
            ) in used_patient:
                continue
            used_doctor.add((doctor, day, hour))
            used_patient.add((patient, day, hour))
            status = (
                "Scheduled"
                if day > AS_OF
                else rng.choices(["Completed", "Cancelled"], weights=[82, 18])[0]
            )
            appointment = add(
                "Appointment",
                AppointmentID=len(tables["Appointment"]) + 1,
                PatientID=patient,
                DoctorID=doctor,
                DepartmentID=dept,
                AppointmentDate=day.isoformat(),
                AppointmentTime=f"{hour:02}:00:00",
                Status=status,
            )
            if status != "Completed":
                continue
            record_id = len(tables["Medical_Record"]) + 1
            medicines = rng.sample(
                range(1, 51), rng.choices([0, 1, 2], weights=[30, 55, 15])[0]
            )
            labels = [f"Demo medicine {m:02}" for m in medicines]
            add(
                "Medical_Record",
                RecordID=record_id,
                PatientID=patient,
                DoctorID=doctor,
                VisitDate=day.isoformat(),
                Diagnosis=f"{departments[dept - 1]} scenario {rng.randrange(1, 5)}",
                TreatmentPlan="Synthetic scenario; not clinical guidance",
                Prescription=" | ".join(labels) if labels else "No prescription",
                AppointmentID=appointment["AppointmentID"],
            )
            for med in medicines:
                add(
                    "Prescription",
                    PrescriptionID=len(tables["Prescription"]) + 1,
                    RecordID=record_id,
                    MedicineID=med,
                    Dosage="Demo dose",
                    Frequency="Demo frequency",
                    Duration="Demo duration",
                )
            paid = rng.random() < 0.86
            payment_day = day + timedelta(days=rng.randrange(0, 22))
            paid = paid and payment_day <= AS_OF
            add(
                "Billing",
                BillingID=len(tables["Billing"]) + 1,
                PatientID=patient,
                TotalAmount=round(rng.uniform(80, 900) * (1 + dept * 0.12), 2),
                PaymentStatus="Paid" if paid else "Unpaid",
                PaymentDate=payment_day.isoformat() if paid else None,
                PaymentMethod=rng.choice(["Card", "Cash", "Transfer"])
                if paid
                else None,
                RecordID=record_id,
            )
            if rng.random() < 0.18 and patient_free[patient] <= day:
                rooms = [
                    r
                    for r in tables["Room"]
                    if r["DepartmentID"] == dept and room_free[r["RoomID"]] <= day
                ]
                if rooms:
                    room = rng.choice(rooms)
                    stop = day + timedelta(days=rng.randrange(1, 7))
                    discharge = stop.isoformat() if stop <= AS_OF else None
                    add(
                        "Room_Assignment",
                        AssignmentID=len(tables["Room_Assignment"]) + 1,
                        RoomID=room["RoomID"],
                        PatientID=patient,
                        AdmissionDate=day.isoformat(),
                        DischargeDate=discharge,
                    )
                    room_free[room["RoomID"]] = stop
                    patient_free[patient] = stop
    occupied = {
        r["RoomID"] for r in tables["Room_Assignment"] if r["DischargeDate"] is None
    }
    for room in tables["Room"]:
        room["AvailabilityStatus"] = (
            "Occupied" if room["RoomID"] in occupied else "Available"
        )
    return tables


def sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    return "N'" + value.replace("'", "''") + "'"


def write():
    tables = generate()
    out = ROOT / "data/processed"
    out.mkdir(parents=True, exist_ok=True)
    metadata = {
        "synthetic": True,
        "seed": SEED,
        "as_of": AS_OF.isoformat(),
        "assumptions": [
            "Single-person rooms; admissions inclusive and discharges exclusive",
            "Scenario diagnoses and medicines are illustrative, not clinical recommendations",
            "Booked future appointments; settled outcomes through the fixed snapshot date",
        ],
        "tables": {},
    }
    statements = [
        "-- Generated by scripts/generate_data.py; synthetic demonstration only.",
        "-- Load once after model.sql in an empty database. Failure rolls back every insert.",
        "SET XACT_ABORT ON;",
        "BEGIN TRY",
        "BEGIN TRANSACTION;",
    ]
    for table, rows in tables.items():
        columns = list(rows[0])
        path = out / f"{table}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        metadata["tables"][table] = {
            "rows": len(rows),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        # SQL Server table-value constructors accept at most 1,000 rows.
        for start in range(0, len(rows), 500):
            values = [
                "(" + ",".join(sql_literal(row[c]) for c in columns) + ")"
                for row in rows[start : start + 500]
            ]
            statements.append(
                f"INSERT dbo.{table} ({','.join(columns)}) VALUES\n"
                + ",\n".join(values)
                + ";"
            )
    statements += [
        "COMMIT TRANSACTION;",
        "END TRY",
        "BEGIN CATCH",
        "IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;",
        "THROW;",
        "END CATCH;",
    ]
    (ROOT / "sql/inserts.sql").write_text(
        "\n".join(statements) + "\n", encoding="utf-8"
    )
    (out / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({t: len(r) for t, r in tables.items()}))


if __name__ == "__main__":
    write()
