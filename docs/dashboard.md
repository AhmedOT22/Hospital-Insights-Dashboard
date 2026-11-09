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
5. Confirm financial cohort labels and the visit-month footnotes remain clear.
6. Save the compiled PBIX and replace historical screenshots with actual renders.

Until these steps pass, this is implemented **source awaiting Desktop acceptance**,
not a claim that the compiled dashboard is finished. The original PBIX/screenshots
remain historical and intentionally have not been relabelled as new screenshots.

## Chart selection

Every chart answers a different question: no category/measure pair appears twice in
the report. Monthly trends use completed/cancelled outcomes, patients served,
prescriptions or outstanding amounts, never total bookings, because January 2026
contains only future scheduled appointments and would read as a collapse. Future
bookings have their own department chart on the Appointments page.

Comparisons that are flat in the generated data were removed rather than shown as
near-identical bars: gender (100/100), department collection rate (83–86%),
department cancellation rate (17–19%), room occupancy (4 of 20 rooms occupied at the
snapshot), weekday, hour and average stay. Their measures stay in the model and in the
acceptance checks. The Doctors page gives its two charts the full chart-area height
so all 20 doctors fit without scrolling. Theme series colors keep at least 3:1
contrast on white. `tests/test_pipeline.py` enforces these rules.

## Accessibility

Every visual carries alt text (`visualContainerObjects.general.altText`): charts
name their type and title, cards their measure, slicers the field they filter and
textboxes their visible text. Navigation buttons also have a `visualLink` tooltip
("Go to the … page" / "… (current page)"). Power BI focuses the **highest**
`tabOrder` first, so the generator assigns values from N × 1000 down to 1000 in
reading order: heading, context line, navigation, KPI cards, charts, slicers,
footnote. `tests/test_pipeline.py` enforces all three. Screen-reader output and
focus order still need a manual check in Desktop (step 4 above).

## Final source audit

The cards use the native `cardVisual` / `Data` binding. Navigation uses explicit
default-state text/fill/shape selectors, a selected-page color and 44 px buttons.
Dropdown slicers reserve 80 px for their headers, selector and padding. Source
checks catch invalid role names, nonexistent navigation destinations and overlapping
visual containers. They cannot establish the final rendered appearance.

Generate acceptance fixtures with `python -m scripts.reconcile_metrics` after data
or measure changes. The committed expected values come from CSV joins and Decimal
arithmetic, independently of DAX. Do not regenerate them to conceal a failed check.
