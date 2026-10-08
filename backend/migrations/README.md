# Database setup — next step

Supabase/PostGIS provisioning and executable migrations are not included in this initial half-day setup.

After verifying database access and the data contract, add versioned SQL migrations here for stations with spatial coordinates, sensor observations, snapshot manifests and route comparison cache entries. Install PostGIS in a dedicated schema, not `public`. Use the API for database access; do not expose database credentials in the browser.

See the [implementation plan](../../documentations/IMPLEMENTATION_PLAN.md) for the cache key and validation requirements.
