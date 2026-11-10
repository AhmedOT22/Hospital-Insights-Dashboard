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
| Executive Overview | Unpaid amount by visit age, collected vs unpaid by department, patients served by month |
| Appointments | Completed and cancelled trends, cancellation rate by month, future bookings by department |
| Departments | Activity, average bill per visit, unpaid over 90 days and completed room stays by department |
| Doctors | Workload and cancellation rate for all 20 doctors; orange marks above the hospital average |
| Patients | Patients served and outcomes by age; prescriptions by visit month across the full period |

Every KPI card carries a context line under its value: a share ("81% is over 90
days old"), a comparison ("+3.8% in 2025 vs 2024") or a range ("83–335 completed per
doctor"). One headline card per page is drawn in orange. Bar and column charts print
their values instead of a value axis, and doctor charts color the bars above the
hospital-wide average in orange.

The redesign uses the "Ward" theme (sage-white canvas, deep teal, orange only for attention), consistent cards, titles,
page navigation and department/month/doctor slicers. Native visuals replace the original
custom histogram. Measures use linked records rather than disconnected summary tables.

**Power BI Desktop acceptance is pending:** the project files pass structural and
published PBIR schema checks, but they have not been opened, refreshed or rendered in
Desktop here. Native DAX evaluation, navigation behavior and visual layout still need
that check. The original `PowerBI/Hospital.pbix` and `screenshots/` remain historical
references; they do not show the redesigned project or corrected dataset.

## Dashboard preview

[View the five-page Ward theme preview](docs/hospital-insights-preview.html). This is an illustrative HTML rendering of the uploaded PBIR layout and synthetic data, not a Power BI Desktop screenshot; slicers and filters are not interactive. The validated source of truth remains `PowerBI/Hospital.pbip`.

## Reproduce

1. Use SQL Server 2022+ and select an empty user database named `HospitalInsights`.
2. Execute `sql/model.sql`, then `sql/inserts.sql` using SSMS or `sqlcmd -b`.
3. Open `PowerBI/Hospital.pbip` in current Power BI Desktop with project/enhanced
   report format support enabled as needed.
4. In **Transform data → Edit parameters**, set `ServerName` and `DatabaseName` to
   your SQL Server instance/database. Authenticate locally and refresh.
5. Run `PowerBI/Hospital.SemanticModel/DAXQueries/Acceptance.dax` in DAX Query View;
   all 544 checks must pass. Review all five pages and save a newly compiled PBIX.

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

[Metric definitions and filter behavior](docs/metrics.md) ·
[Design and acceptance checklist](docs/dashboard.md) ·
[CI runs](https://github.com/AhmedOT22/Hospital-Insights-Dashboard/actions)

Developed by [Ahmed Ouazzani](https://github.com/AhmedOT22).
