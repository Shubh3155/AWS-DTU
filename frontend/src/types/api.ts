export type Coordinate = { lat: number; lng: number };

export type ComparisonRequest = {
  origin: Coordinate;
  destination: Coordinate;
  max_detour_minutes: number;
  mode: "walking";
  data_mode: "live" | "replay";
  snapshot_id?: string;
};

export type HealthResponse = {
  status: "ok";
  service: string;
  version: string;
  environment: string;
};

export type PilotResponse = {
  status: "pending_data_audit";
  boundary: null;
  supported_mode: "walking";
  data_mode: "unavailable";
  warning: string;
};

export type RouteCandidate = {
  id: string;
  geometry: { type: "LineString"; coordinates: [number, number][] };
  distance_metres: number;
  duration_seconds: number;
  estimated_exposure: number | null;
  exposure_unit: "µg·min/m³";
  within_budget: boolean;
  coverage_percent: number;
  via?: Coordinate | null;
};
export type ComparisonResponse = {
  status: "comparison_available" | "uncertain_difference" | "no_lower_exposure_candidate" | "single_candidate" | "limited_data" | "no_route";
  candidates: RouteCandidate[];
  fastest_id: string | null;
  lowest_exposure_eligible_id: string | null;
  estimated_reduction_percent: number | null;
  warnings: string[];
  data_quality: {
    data_mode: "live" | "replay" | "unavailable";
    observed_from: string | null;
    observed_to: string | null;
    fetched_at: string | null;
    source_ids: string[];
    provider_ids: string[];
    data_version: string | null;
    model_version: string | null;
    snapshot_id: string | null;
    reference_time: string | null;
    station_count: number;
    model_parameters: Record<string, number>;
  };
};
