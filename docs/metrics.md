# Measure definitions and filter behavior

The model imports the eleven dbo tables through SQL Server. `ServerName` and
`DatabaseName` are Power Query parameters; credentials stay in Desktop, outside Git.
There is no SPARCS or real patient data. All amounts are demo currency units.

## Activity and financial measures

| Measure | Definition |
| --- | --- |
| Appointments | Count of appointment rows, including future scheduled rows |
| Completed / cancelled / scheduled | Appointment count restricted to the recorded status |
| Completion / cancellation rate | Completed or cancelled divided by completed + cancelled; future scheduled rows excluded; zero for an empty numerator when outcomes exist; blank if denominator is zero |
| Patients served | Distinct patients with completed appointments in the selected activity context |
| Repeat patients | Patients with more than one completed appointment within the current selection |
| Visits | Medical record count; the generated dataset has one linked record per completed appointment |
| Prescriptions | Structured prescription rows; patients can have zero, one or multiple rows per visit |
| Billed amount | Sum of bill amounts, counted once through the linked visit |
| Collected / outstanding | Billed amount with paid / unpaid status; snapshot settlement state |
| Collection rate | Collected divided by billed; zero for no collections when billed exists; blank for a zero denominator |
| Doctors with appointments | Distinct physicians with appointments in the current activity selection |
| Department doctors / staff | Registered workforce by current home department; no combined deduplicated workforce total |
| Rooms / occupied rooms | Single-person room inventory / occupied room snapshot at Dec 31, 2025 |
| Snapshot occupancy | Occupied room count divided by room count; not a historical occupancy trend |
| Completed stays / average completed stay | Closed stay count / mean discharge-minus-admission days; open stays excluded |

Monthly charts and month slicers use a full `yyyy-MM` appointment month, sorted
chronologically. Activity filters flow from appointments to medical records, then
prescriptions and bills. Financial measures therefore describe **appointment cohorts
with settlement status at the snapshot**, not monthly cash receipts by payment date.
Never describe billed amount as collected revenue. No arbitrary revenue targets exist.

## Relationships

Active paths are single-direction from the one side to the many side. Department
filters appointments by recorded service department. Doctor filters appointments;
patient filters appointments and room assignments. Appointment filters medical
records; medical records filter prescriptions and billing. Medicine filters prescriptions.
Room and department filter room assignments through room inventory.

Operational links that would create duplicate filter paths are inactive: the
patient/doctor direct links to medical records, patient direct link to billing and
home department direct link to doctors. Department doctor headcount explicitly uses
TREATAS to apply the selected department to Doctor.DepartmentID. There are no
bidirectional relationships or disconnected summary tables.

Doctor and patient dimension lists do not automatically shrink under a fact-table
month filter; their **activity measures** do respond. Department resource cards remain
home-department snapshots, not staffing levels on an appointment date. Age groups
are calculated at the fixed snapshot date, not at each encounter. Counts of patients
served across departments/doctors are not additive because one person may appear
in multiple groups. Historical unlinked records are not part of the corrected seed.

Data consistency and financial attribution have Python/SQL checks. DAX expressions
and field names are source-validated; their actual evaluation and slicer behavior
must still be accepted in Power BI Desktop.
