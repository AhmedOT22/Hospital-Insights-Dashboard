# SQL Server schema

`model.sql` is a clean-database bootstrap for **SQL Server 2022+**. Select a user
database in SSMS, or use `sqlcmd -b -d YourDatabase -i sql/model.sql`. It does not
create a server/database, drop existing data or migrate an existing installation.
Existing hospital table names cause an explicit error. Creation is transactional;
a failure rolls the schema changes back. Use an explicit migration for an existing
database rather than rerunning the bootstrap.

## Relationships and rules

All eleven original tables and original columns remain. Tables are ordered by
foreign-key dependencies. New optional columns can be omitted from explicit-column
INSERTs. Existing IDs remain caller-assigned, so no IDENTITY_INSERT is needed.

- Foreign keys use SQL Server's default `NO ACTION` for deletion and updates.
  Referenced patients, doctors, departments, medicines and records cannot be removed
  while history depends on them. `IsActive` supports deactivation of people and
  departments; `Doctor.Availability` remains a separate availability flag.
- Required names, dates, amounts and statuses are explicit. Amounts and stock cannot
  be negative. Unicode names/notes use NVARCHAR; deprecated TEXT is removed.
  Patient gender is optional descriptive data, without an unnecessarily binary enum.
  Contacts can be missing or shared; phone/email are not identity keys.
- Non-cancelled appointments cannot share a doctor's or patient's start date/time.
  Cancelled appointments remain in history and release their slots. This does not
  enforce duration-based scheduling: there is no appointment end-time field yet.
- `Medical_Record.AppointmentID` optionally links a visit to an appointment. A
  composite foreign key enforces the same patient and doctor. Null allows walk-ins
  and legacy unlinked visits. Multiple notes/records can reference one appointment;
  same-day visit timing and completed status are not automatically enforced.
- `Billing.RecordID` optionally links a bill to a visit. Its composite foreign key
  enforces the same patient. Bills may remain unlinked; do not infer their department
  from all appointments belonging to that patient. For linked bills, use the visit's
  linked appointment department. Unlinked revenue must remain explicitly unattributed.
- Billing supports full payment or no payment: paid rows require a date and nonblank
  method; unpaid rows require both to be null. Partial payments/refunds would need
  a separate payment model, not made-up values in these fields.
- `Medical_Record.Prescription` remains for Power BI/legacy column compatibility,
  but is narrative only. Structured `Prescription` rows joined to `Medicine` are the
  medication source of truth; free-text agreement is not enforced.
- `Room_Assignment` requires admission dates and prevents discharge before admission.
  `Room.AvailabilityStatus` remains a legacy snapshot, not an automatically derived
  occupancy measure. No bed-capacity or historical-overlap rule is claimed. Reliable
  occupancy/length-of-stay reporting needs coherent assignments and a defined bed model.
- Appointment department is the recorded service department; doctor department is
  their current home department. Equality is not enforced, since legitimate service
  outside a home department or later transfers must not rewrite appointment history.
  Staff and Doctor remain separate registries; do not add their counts as a deduplicated
  workforce total without a common person identity.

Named constraints make failures identifiable. Indexes support common patient/date,
department/date, prescription and billing joins; they are not a performance benchmark.

## Original generated rows

`inserts.sql` has not been regenerated. It contains, among other issues:

- 68 unpaid bills carrying payment dates/methods, rejected by the billing rule.
- Non-cancelled appointments 337 and 387 with the same doctor/start time, rejected
  by the unique scheduling index.
- Seven occupied room snapshots but no room assignments.
- Contradictory prescription narratives, doctor/department mappings and an adult-only
  pediatric population. Foreign keys alone cannot establish realistic synthetic data.

**Do not treat this file as a clean seed or run it blindly after schema creation.**
Without an enclosing transaction, its independent INSERT statements can leave a
partially loaded database after an error. Generate and validate a coherent replacement
before refreshing the dashboard. This update deliberately does not relabel payments,
appointments or clinical details to make invalid rows pass.

## Verification

`.github/workflows/schema.yml` runs the actual DDL and `tests/schema.sql` on a
SQL Server 2022 Developer container. The test creates valid linked rows, exercises
28 invalid-data/deletion cases, verifies deactivation preserves records, then rolls
its fixtures back. A second bootstrap attempt must fail without changing the schema.
Run these checks only in a fresh disposable user database, not over existing data.
The tests do not certify the original seed or the Power BI measures/relationships.
