from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.routes import Coordinate


class StationObservation(BaseModel):
    """Normalized input contract. Raw OpenAQ units must be checked before normalization."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    sensor_id: int = Field(gt=0)
    station_id: int = Field(gt=0)
    location: Coordinate
    pm25_micrograms_per_m3: float = Field(ge=0, strict=True)
    observed_at: AwareDatetime
    fetched_at: AwareDatetime
    provider_id: str


class ConcentrationEstimate(BaseModel):
    """Missing evidence remains null; it must never be substituted with zero."""

    model_config = ConfigDict(allow_inf_nan=False)
    pm25_micrograms_per_m3: float | None = Field(default=None, ge=0)
    supporting_sensor_ids: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
