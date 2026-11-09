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

## KPI context and highlight measures

These feed the context line under each KPI card and the above-average bar colors.
They are ordinary numeric measures, checked by the CSV, SQL and DAX acceptance cases
like every KPI above.

| Measure | Definition |
| --- | --- |
| Completed YoY change | Completed appointments in 2025 versus 2024, as a change ratio; blank when the selection holds no 2024 completions; −100% when it holds 2024 but not 2025 |
| Outstanding over 90 days | Unpaid amount for visits more than 90 days before the Dec 31, 2025 snapshot (visit date before Oct 2, 2025) |
| Outstanding over 90 days share | Outstanding over 90 days divided by outstanding amount |
| Average bill per visit | Billed amount divided by visits |
| Visits per patient | Completed appointments divided by patients served |
| Highest / lowest doctor workload | Largest / smallest completed-appointment count among doctors in the selection; doctors with no completions are ignored |
| Average completed per doctor | Completed appointments divided by doctors with appointments, ignoring any doctor filter |
| Highest doctor cancellation rate | Largest per-doctor cancellation rate in the selection |
| Cancellation rate all doctors | Cancellation rate ignoring any doctor filter: the hospital-wide benchmark |

Card notes (display folder *Card notes*) are text measures that format the values
above, for example "81% is over 90 days old"; they return "No data for this
selection" instead of a fragment when their input is blank. The two *Highlight colors*
measures return orange when a doctor's completed appointments or cancellation rate
exceeds the hospital-wide figure, and slate grey otherwise; they color bars per data point.
`Billing[Visit age band]` groups bills by the age of their linked visit at the snapshot
(0–30, 31–90, 91–365, over 365 days) for the unpaid-amount aging chart.

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
