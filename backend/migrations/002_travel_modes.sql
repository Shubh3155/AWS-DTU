-- Preserve existing rows and extend the backend-only route cache modes.
ALTER TABLE aeroroute.route_comparison_cache
    DROP CONSTRAINT route_comparison_cache_mode_check;
ALTER TABLE aeroroute.route_comparison_cache
    ADD CONSTRAINT route_comparison_cache_mode_check
    CHECK (mode IN ('walking', 'driving', 'motorcycle'));
