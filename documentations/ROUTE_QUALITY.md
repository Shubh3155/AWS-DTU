# Walking candidate quality — 9 October 2026

The fastest actual provider route is retained. Optional native or waypoint
alternatives are screened before scoring; provider geometry and step timings are
never shortened, redrawn or replaced. Filtering may leave one candidate.

The fixed prototype rules reject:

- Duration or reported distance over 1.8 times the fastest provider candidate.
- Substantial retracing in the opposite direction: more than the larger of
  80 metres or 5% of geometric path length.
- A return to a nearby point in the same direction after over 200 metres of travel,
  used as a conservative closed-loop heuristic.
- Near-duplicate paths: at least 90% shared corridor in both directions, using a
  12-metre proximity tolerance.
- Geometry exceeding bounded sampling work (10,000 samples, 128 samples per cell).

Checks use local projected coordinates, samples no farther than 20 metres apart
and a spatial index. Thresholds are engineering heuristics, not validated walking
preferences. Nearby parallel paths can be treated as similar; an unusual but
legitimate alternative can be rejected. The fastest source route is preserved
even when its shape triggers a heuristic. These checks do not establish pedestrian
access, road safety, route exhaustiveness or pollution benefits.

Six previously saved genuine Mapbox journeys were reviewed without changing their
paths. The filter removes five backtracking alternatives from eighteen candidates,
retaining the fastest in every case. Four journeys lose one or two alternatives;
the central-east demo keeps all three. [Results](ROUTE_QUALITY_RESULTS.json) record
case counts, rejected IDs/reasons and the input hash. Raw geometry remains local.

The routing cache contract is now `walking-steps-v3-quality`, so older unfiltered
route sets cannot survive a cache hit. Provider request limits and optional-probe
failure behavior remain bounded. Unit checks cover real failure modes: out-and-back
paths, closed loops, changed vertex density, small turns, parallel alternatives,
excessive detours, sampling limits and preservation of a sole provider path.

After updating the backend, ten genuine demo requests again passed allowance
checks and returned supported historical scores. Offline screening of saved routes
does not replace inspection of pedestrian conditions or deployed testing.
