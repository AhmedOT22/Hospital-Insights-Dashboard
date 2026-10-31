# Five-page redesign and Desktop acceptance

The approved scope retains eleven synthetic business tables and the original five
analytical areas. Executive Overview replaces Department Performance. The editable
source is Hospital.pbip with PBIR report definitions and model.bim semantic metadata.
No binary DataModel or legacy report layout was patched: those formats cannot be
reliably compiled or visually verified without Power BI Desktop here.

The source implements a 16:9 canvas, light clinical blue/teal theme, Segoe UI,
consistent navigation/cards and two-column chart grids. Redundant patient-distribution
charts, physician contact tables, stock photos, custom histogram, disconnected totals
and unsupported KPI targets are removed from the redesigned project. Department and
appointment-month slicers replace repeated hard-coded department charts.

## Data completed

- Reproducible generation (seed 42), with 4,338 appointments and 3,519 linked visits/bills.
- Pediatric patients and doctor specializations match their generated departments.
- Explicit future scheduled appointments; no future payments or completed outcomes.
- Prescription narratives agree with structured rows; no prescriptions for records
  labelled 'No prescription'. Scenario drugs/doses are illustrative, not medical guidance.
- 618 room stays obey the single-person-room assumption, avoid patient/room overlap
  and reconcile with the occupied-room snapshot.
- Unpaid payment details are null, paid details are populated, and encounter-linked
  financial totals reconcile without patient-based join multiplication.

## Power BI Desktop acceptance still required

1. Open Hospital.pbip; confirm the semantic model loads without metadata errors.
2. Set SQL parameters, refresh and compare row counts with data/processed/manifest.json.
3. Run `DAXQueries/Acceptance.dax` from the semantic model folder in Desktop DAX
   Query View after refresh. All **374 rows** must return `Passed = TRUE`. The
   independent CSV oracle covers all 22 measures across 17 contexts: departments,
   months, doctor/patient/status selections, a future-only period, an empty period
   and an incompatible doctor/department. It distinguishes BLANK from zero.
   `tests/metrics.sql` runs matching SQL checks in CI; passing SQL does not prove DAX.
4. Confirm card formatting, theme loading, navigation buttons, slicers, labels and
   chronological axes on every page. Check 100% zoom, contrast, keyboard order and
   charts with long labels. Adjust native visual properties if Desktop needs them.
5. Confirm financial cohort labels and fixed snapshot resource cards remain clear.
6. Save the compiled PBIX and replace historical screenshots with actual renders.

Until these steps pass, this is implemented **source awaiting Desktop acceptance**,
not a claim that the compiled dashboard is finished. The original PBIX/screenshots
remain historical and intentionally have not been relabelled as new screenshots.

## Final source audit

The cards use the native `cardVisual` / `Data` binding. Navigation uses explicit
default-state text/fill/shape selectors, a selected-page color and 44 px buttons.
Dropdown slicers reserve 80 px for their headers, selector and padding. Source
checks catch invalid role names, nonexistent navigation destinations and overlapping
visual containers. They cannot establish the final rendered appearance.

Generate acceptance fixtures with `python -m scripts.reconcile_metrics` after data
or measure changes. The committed expected values come from CSV joins and Decimal
arithmetic, independently of DAX. Do not regenerate them to conceal a failed check.
