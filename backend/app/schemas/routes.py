from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class Coordinate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    lat: float = Field(ge=-90, le=90, strict=True)
    lng: float = Field(ge=-180, le=180, strict=True)


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    origin: Coordinate
    destination: Coordinate
    max_detour_minutes: float = Field(ge=0, strict=True)
    mode: Literal["walking"] = "walking"
    data_mode: Literal["live", "replay"] = "live"
    snapshot_id: str | None = Field(default=None, min_length=1, max_length=200)


class LineString(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]] = Field(min_length=2)

    @field_validator("coordinates", mode="before")
    @classmethod
    def valid_positions(cls, values: list[tuple[float, float]]) -> list[tuple[float, float]]:
        for pair in values:
            if len(pair) != 2 or any(type(value) not in (int, float) for value in pair):
                raise ValueError("Coordinates must contain numeric longitude/latitude pairs")
            lng, lat = pair
            Coordinate(lat=lat, lng=lng)
        return values


class RouteCandidate(BaseModel):
    id: str
    geometry: LineString
    distance_metres: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    estimated_exposure: float | None = Field(default=None, ge=0)
    exposure_unit: Literal["µg·min/m³"] = "µg·min/m³"
    within_budget: bool
    coverage_percent: float = Field(ge=0, le=100)


class DataQuality(BaseModel):
    data_mode: Literal["live", "replay", "unavailable"]
    observed_from: AwareDatetime | None = None
    observed_to: AwareDatetime | None = None
    fetched_at: AwareDatetime | None = None
    source_ids: list[str] = Field(default_factory=list)
    provider_ids: list[str] = Field(default_factory=list)
    data_version: str | None = None
    model_version: str | None = None
    snapshot_id: str | None = None
    reference_time: AwareDatetime | None = None
    station_count: int = Field(default=0, ge=0)
    model_parameters: dict[str, float | int] = Field(default_factory=dict)


class ComparisonResponse(BaseModel):
    """Evaluated walking routes, model estimates and explicit data-quality metadata."""

    status: Literal[
        "comparison_available",
        "uncertain_difference",
        "no_lower_exposure_candidate",
        "single_candidate",
        "limited_data",
        "no_route",
    ]
    candidates: list[RouteCandidate]
    fastest_id: str | None
    lowest_exposure_eligible_id: str | None
    estimated_reduction_percent: float | None
    warnings: list[str]
    data_quality: DataQuality


class PilotResponse(BaseModel):
    status: Literal["pending_data_audit"] = "pending_data_audit"
    boundary: None = None
    supported_mode: Literal["walking"] = "walking"
    data_mode: Literal["unavailable"] = "unavailable"
    warning: str = "A Delhi pilot boundary will be selected after monitoring coverage is verified."
