# Three-minute historical MVP demo

This release demonstrates **time-budgeted route comparison with provisional
historical exposure estimates**. It does not promise current air quality, measured
health benefits or a validated cleaner route. The October snapshot is genuine;
walking paths are obtained from the current provider. No synthetic result is
substituted if an upstream service fails.

## Before presenting

Open the running app. Check connection, then select **Try recorded Delhi journey**
and **Compare walking routes**. The preset fills the reviewed endpoints, selects
historical replay and sets a five-minute allowance. Verify original observation
dates and scores before starting. A cold request can take several seconds.

Today's genuine check returns three candidates. Provider paths may change;
present the actual response rather than forcing the old counts or estimates.

## Walkthrough

| Time | Action and explanation |
| --- | --- |
| 0:00–0:25 | “AeroRoute compares cumulative estimated pollution exposure within the extra walking time you can afford. A longer walk can increase exposure even when air concentration is lower.” |
| 0:25–1:00 | Load the recorded Delhi journey and compare. Show durations and the green path. Hover/focus cards to preview; select a route on mobile. |
| 1:00–1:30 | Set allowance to 0 and compare: only the fastest is eligible today. Set 5: the second is eligible. Set 15: all three are eligible. Eligibility uses exact durations, not rounded labels. |
| 1:30–2:00 | Show the counterexample: the fastest has the lowest estimate here. More walking is not automatically a better pollution decision. No improvement percentage is invented. |
| 2:00–2:30 | Point to October 2025 observation dates and replay labels. Explain sparse stations and provisional interpolation. Validation varies substantially across October, November and December. |
| 2:30–2:45 | Switch replay off and compare. Today's audit has only one fresh station, below three required; scores stay unavailable. If actual live coverage changes, show the current result honestly. |
| 2:45–3:00 | After deployment, show the public connection and release version. State that field validation, dependable live coverage and a robust beneficial detour remain future work. |

## Claims to use

- Genuine provider walking paths, screened for obvious circuitous/similar alternatives.
- Exact detour eligibility; estimated cumulative exposure accounts for time.
- Clear provenance, historical timestamps and missing-data behavior.
- Reproducible station holdouts, honest error reporting and passing automated checks.

The USP is the decision workflow and transparency. A reliable positive pollution
benefit has **not** been demonstrated. The video itself must include the deployed
URLs, so final recording follows AWS deployment.
