export type Coordinate = { lat: number; lng: number };

export type ComparisonRequest = {
  origin: Coordinate;
  destination: Coordinate;
  max_detour_minutes: number;
  mode: "walking";
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
