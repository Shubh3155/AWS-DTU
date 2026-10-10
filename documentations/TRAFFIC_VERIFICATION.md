# Traffic-profile verification — 10 October 2026

A direct Mapbox Directions request used the public Delhi demo endpoints
(77.2167, 28.6315) → (77.2410, 28.6280), `driving-traffic`, steps, full GeoJSON,
native alternatives and `congestion,distance,duration` annotations. No user GPS was used.
The configured token was read locally; credentials and token-bearing URLs were not logged.

The provider returned HTTP 200 / `Ok` and two real routes:

| Route | Provider duration | Typical duration | Congestion labels |
| --- | ---: | ---: | --- |
| 1 | 464.901 s | 560.312 s | 90 unknown segments |
| 2 | 478.511 s | 584.643 s | 143 unknown segments |

**This verifies access to the traffic profile, not live congestion coverage for Delhi.**
All reported congestion labels were unknown. Different durations do not prove live segment
observations; Mapbox combines available current and historical traffic information.
The application retains provider travel times, displays unavailable congestion explicitly,
and does not fabricate congestion or treat unknown as clear. Typical-time differences may
be positive or negative and are not labelled as guaranteed delays.

Route and step times feed the existing detour budget and ambient exposure model. Traffic does
not supply pollution observations, cabin air or inhaled-dose estimates. Motorcycle retains
car routing/time approximations with explicit restrictions/speed limitations.

Vehicle caches are bounded to 60 seconds. Navigation refreshes remaining routes about every
two minutes with accurate foreground GPS; the selected route can change after re-comparison.
Stop cancels updates. Browser tests use synthetic traffic/GPS, with real field testing pending.

Reference: [Mapbox Directions API](https://docs.mapbox.com/api/navigation/directions/).
