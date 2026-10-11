# Live route-region air quality

Live comparisons now request current PM2.5 forecasts from the
[Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api)
for regions crossed by the actual Mapbox paths. They do not read pollution
snapshots or routing caches from Supabase. Historical replay continues to use
the selected OpenAQ snapshot and the existing station interpolation policy.

## Why the production scores were unavailable

The previous live path loaded the most recently ingested `live` database
snapshot, without refreshing it from a provider. Fetch time did not make its
observations current. Once the readings were older than the two-hour policy,
station support fell to zero. Even a fresh snapshot could fail where fewer than
three distinct nearby stations were available.

The new source is a **regional model forecast**, not a set of measured stations.
It uses CAMS Global, with approximately 45 km spatial resolution. Nearby Delhi
alternatives can occupy the same model cell and therefore have identical modeled
concentrations; their exposure difference then comes from travel time. This
change improves current data availability, not demonstrated street-level accuracy
or evidence for a beneficial cleaner detour.

## Request and scoring flow

1. Obtain genuine walking or driving-traffic geometry and preserved step durations.
2. Subdivide steps at the existing 100 m maximum interval, retaining waiting time.
3. Deduplicate route sampling regions on a 0.02-degree query grid. For long routes,
   coarsen queries up to the provider's 0.4-degree resolution. A request fetches at
   most 64 locations in one batch. If the coarsest grid still exceeds this bound,
   unsampled regions remain unsupported; no values are extrapolated into them.
4. Request `current=pm2_5`, `domains=cams_global`, UTC Unix timestamps, and one
   forecast day. Check units, finite non-negative concentrations, grid coordinates,
   response cardinality, and whether each current interval covers server time.
5. Sum `PM2.5 × segment duration in minutes`. Coverage is supported travel time
   divided by full route duration. Partial support withholds the full-route score.

This calculation holds the current regional field fixed throughout the journey.
It does not predict conditions at arrival or model breathing rate/cabin filtration.
The three-station minimum still applies to recorded station interpolation; forecast
grid samples never become synthetic monitoring stations.

## Caching and failures

- A bounded 256-entry process cache shares regional queries for at most 180 seconds,
  and never past each forecast interval's end. Scoring checks validity again even
  when routing geometry is a cache hit.
- Concurrent cold reads are coalesced so callers share the refreshed region data.
- Geometry is cached separately in memory; driving/motorcycle TTL is at most
  60 seconds. Allowance changes reuse geometry and recalculate eligibility.
- Missing/invalid region responses have a 15-second negative cache. Provider errors
  have a 15-second cooldown; HTTP 429 has a 60-second cooldown. Fresh already-cached
  regions may still support their portions of a route. Expired data is not reused.
- Requests have a six-second provider timeout. API failures retain genuine routes
  with explicit warnings and null unsupported exposure scores.

The public Open-Meteo endpoint needs no API key for this non-commercial prototype.
No additional AWS resource, database migration, or frontend secret is required.

## Response and display

Forecast responses declare `source_type: model_forecast`, forecast `valid_from` /
`valid_to`, fetch time, sampling-region count, grid source IDs, approximately 45 km
resolution, model/data versions, and Open-Meteo/Copernicus attribution. They have
zero monitoring stations, no observed-time range, and no database snapshot ID.

The page displays **Air-quality time coverage**, forecast validity, and regional
resolution. Coverage of 100% means every sampled travel interval has provider data;
it does not mean 100% accuracy. Reduction percentages remain suppressed.

## Verification on 11 October 2026

The updated local API was exercised with genuine Mapbox routes and current
Open-Meteo responses for the recorded Delhi endpoints, with replay disabled:

- Three walking candidates and two driving candidates returned non-null exposure
  estimates, each with 100% time coverage.
- Four requested sampling regions mapped to one actual CAMS grid cell. The provider
  values were valid from 10:00 to 11:00 UTC; sampling regions were not called stations.
- No Supabase snapshot was selected. This verified the local implementation against
  real providers, not a deployed release or a model accuracy claim.

Automated tests cover route interiors, batch/deduplication, long-route bounds,
invalid units/values/times/coordinates, travel-time weighting, partial coverage,
interval expiry, rate-limit backoff, replay isolation, and all three live travel
modes bypassing the database. Browser checks exercise the forecast notice and
attribution at desktop/mobile sizes using clearly synthetic responses.

Deploy both the frontend and backend through the existing Amplify and Lightsail VM
release paths, then verify live and replay comparisons against the public URLs.
