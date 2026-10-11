-- Run as the database owner after creating the private LOGIN role.
-- No passwords are stored here. This role cannot ingest or migrate data.
GRANT CONNECT ON DATABASE postgres TO aeroroute_runtime_aws;
GRANT USAGE ON SCHEMA aeroroute, gis TO aeroroute_runtime_aws;
GRANT SELECT ON aeroroute.stations, aeroroute.observations, aeroroute.snapshots
  TO aeroroute_runtime_aws;
GRANT SELECT, INSERT, UPDATE, DELETE ON aeroroute.route_comparison_cache
  TO aeroroute_runtime_aws;
DO $$
DECLARE relation_name text;
BEGIN
  FOREACH relation_name IN ARRAY ARRAY['stations', 'observations', 'snapshots'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='aeroroute'
        AND tablename=relation_name AND policyname='aws_runtime_read') THEN
      EXECUTE format('CREATE POLICY aws_runtime_read ON aeroroute.%I FOR SELECT TO aeroroute_runtime_aws USING (true)', relation_name);
    END IF;
  END LOOP;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='aeroroute'
      AND tablename='route_comparison_cache' AND policyname='aws_runtime_cache') THEN
    CREATE POLICY aws_runtime_cache ON aeroroute.route_comparison_cache
      FOR ALL TO aeroroute_runtime_aws USING (true) WITH CHECK (true);
  END IF;
END $$;
