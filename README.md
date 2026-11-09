# Hospital Insights Dashboard

A five-page Power BI demonstration of hospital appointments, service activity,
physician workload and patient patterns. It uses **synthetic data**, SQL Server and
an editable Power BI project. No real hospital performance or clinical conclusions
are claimed.

## Open the redesigned project

The current source is **[PowerBI/Hospital.pbip](PowerBI/Hospital.pbip)**. It contains
an eleven-table semantic model and five 1280 × 720 report pages:

| Page | Purpose |
| --- | --- |
| Executive Overview | Patients served by month, collected amount by department, outcomes, outstanding amount by visit month |
| Appointments | Completed and cancelled trends, cancellation rate by month, future bookings by department |
| Departments | Activity, billed and collected amounts, completed room stays and prescriptions by department |
| Doctors | Completed appointments and cancellation rate for all 20 doctors, without arbitrary targets |
| Patients | Patients served, repeat patients and outcomes by age; prescriptions by visit month |

The redesign uses a neutral background, blue/teal theme, consistent cards, titles,
page navigation and department/month/doctor slicers. Native visuals replace the original
custom histogram. Measures use linked records rather than disconnected summary tables.

**Power BI Desktop acceptance is pending:** the project files pass structural and
published PBIR schema checks, but they have not been opened, refreshed or rendered in
Desktop here. Native DAX evaluation, navigation behavior and visual layout still need
that check. The original `PowerBI/Hospital.pbix` and `screenshots/` remain historical
references; they do not show the redesigned project or corrected dataset.

## Reproduce

1. Use SQL Server 2022+ and select an empty user database named `HospitalInsights`.
2. Execute `sql/model.sql`, then `sql/inserts.sql` using SSMS or `sqlcmd -b`.
3. Open `PowerBI/Hospital.pbip` in current Power BI Desktop with project/enhanced
   report format support enabled as needed.
4. In **Transform data → Edit parameters**, set `ServerName` and `DatabaseName` to
   your SQL Server instance/database. Authenticate locally and refresh.
5. Run `PowerBI/Hospital.SemanticModel/DAXQueries/Acceptance.dax` in DAX Query View;
   all 374 checks must pass. Review all five pages and save a newly compiled PBIX.

The data snapshot is **December 31, 2025**. Bookings extend into January 2026;
completed outcomes, payments and occupancy stop at the snapshot. Currency amounts
are illustrative units. The sample uses single-person rooms and non-clinical scenario
labels/medicines. It is an analytical demonstration, not a hospital scheduling system.

```bash
python -m pip install -r requirements-dev.txt
python scripts/generate_data.py
python scripts/build_powerbi.py
python -m scripts.reconcile_metrics
python -m unittest discover -s tests -v
python scripts/validate_report.py
```

Generation uses seed 42 and exports matching CSV/SQL inputs plus checksums. It
replaces the original inconsistent inserts; those are archived in
`sql/legacy/inserts.sql`. The bootstrap and seed are for an empty database; they
never silently reset an existing installation. See [SQL rules](sql/README.md).

## Evidence and limits

CI runs the schema, 28 rejection cases, the full generated seed and reconciliation
queries on SQL Server 2022, including 374 metric comparisons across 17 filter contexts. It also checks reproducibility, fourteen Python tests,
report field bindings, accessibility metadata, filter paths and Microsoft PBIR JSON schemas. These checks
cover data and source structure, not Desktop rendering or DAX engine correctness.

[Metric definitions and filter behavior](docs/metrics.md) ·
[Design and acceptance checklist](docs/dashboard.md) ·
[CI runs](https://github.com/AhmedOT22/Hospital-Insights-Dashboard/actions)

Developed by [Ahmed Ouazzani](https://github.com/AhmedOT22).
