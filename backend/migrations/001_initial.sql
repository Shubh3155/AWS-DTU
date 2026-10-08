-- Backend-only storage: keep this schema out of Supabase's exposed API schemas.
CREATE TABLE aeroroute.stations (
    provider_id text NOT NULL CHECK (provider_id <> ''),
    station_id bigint NOT NULL CHECK (station_id > 0),
    name text NOT NULL,
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    location gis.geography(Point, 4326) GENERATED ALWAYS AS
        (gis.ST_SetSRID(gis.ST_MakePoint(longitude, latitude), 4326)::gis.geography) STORED,
    metadata jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(metadata) = 'object'),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (provider_id, station_id)
);
CREATE INDEX stations_location_idx ON aeroroute.stations USING gist (location);

CREATE TABLE aeroroute.snapshots (
    snapshot_id text PRIMARY KEY CHECK (snapshot_id <> ''),
    data_version text NOT NULL CHECK (data_version <> ''),
    data_mode text NOT NULL CHECK (data_mode IN ('live', 'replay')),
    observed_from timestamptz NOT NULL,
    observed_to timestamptz NOT NULL,
    fetched_at timestamptz NOT NULL,
    source_manifest jsonb NOT NULL CHECK (jsonb_typeof(source_manifest) = 'object'),
    object_uri text,
    UNIQUE (snapshot_id, data_version),
    CHECK (observed_from <= observed_to),
    CHECK (fetched_at >= observed_to)
);

CREATE TABLE aeroroute.observations (
    snapshot_id text NOT NULL REFERENCES aeroroute.snapshots(snapshot_id),
    provider_id text NOT NULL,
    station_id bigint NOT NULL,
    sensor_id bigint NOT NULL CHECK (sensor_id > 0),
    observed_at timestamptz NOT NULL,
    fetched_at timestamptz NOT NULL CHECK (fetched_at >= observed_at),
    pm25_micrograms_per_m3 double precision NOT NULL
        CHECK (pm25_micrograms_per_m3 >= 0 AND pm25_micrograms_per_m3 < 'Infinity'::float8),
    unit text NOT NULL DEFAULT 'µg/m³' CHECK (unit = 'µg/m³'),
    source_unit text NOT NULL CHECK (source_unit <> ''),
    metadata jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(metadata) = 'object'),
    PRIMARY KEY (snapshot_id, provider_id, sensor_id, observed_at),
    FOREIGN KEY (provider_id, station_id) REFERENCES aeroroute.stations(provider_id, station_id)
);
CREATE INDEX observations_station_time_idx
    ON aeroroute.observations (provider_id, station_id, observed_at DESC);

CREATE TABLE aeroroute.route_comparison_cache (
    cache_key text PRIMARY KEY CHECK (cache_key <> ''),
    origin_latitude double precision NOT NULL CHECK (origin_latitude BETWEEN -90 AND 90),
    origin_longitude double precision NOT NULL CHECK (origin_longitude BETWEEN -180 AND 180),
    destination_latitude double precision NOT NULL CHECK (destination_latitude BETWEEN -90 AND 90),
    destination_longitude double precision NOT NULL CHECK (destination_longitude BETWEEN -180 AND 180),
    mode text NOT NULL CHECK (mode = 'walking'),
    time_bucket timestamptz NOT NULL,
    max_detour_minutes double precision NOT NULL
        CHECK (max_detour_minutes >= 0 AND max_detour_minutes < 'Infinity'::float8),
    snapshot_id text NOT NULL REFERENCES aeroroute.snapshots(snapshot_id),
    data_version text NOT NULL CHECK (data_version <> ''),
    model_version text NOT NULL CHECK (model_version <> ''),
    response jsonb NOT NULL CHECK (jsonb_typeof(response) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL CHECK (expires_at > created_at),
    UNIQUE (origin_latitude, origin_longitude, destination_latitude, destination_longitude,
            mode, time_bucket, max_detour_minutes, snapshot_id, data_version, model_version),
    FOREIGN KEY (snapshot_id, data_version)
        REFERENCES aeroroute.snapshots(snapshot_id, data_version)
);
CREATE INDEX route_comparison_cache_expiry_idx ON aeroroute.route_comparison_cache (expires_at);

ALTER TABLE aeroroute.stations ENABLE ROW LEVEL SECURITY;
ALTER TABLE aeroroute.snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE aeroroute.observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE aeroroute.route_comparison_cache ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA aeroroute FROM PUBLIC, anon, authenticated;
