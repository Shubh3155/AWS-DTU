from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.routes import Coordinate


class DeviceRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient: str = Field(min_length=10, max_length=4096)
    recipient_kind: Literal["token", "fid"] = "token"


class NavigationStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{10,128}$")
    navigation_token: str = Field(pattern=r"^[a-f0-9]{32}$")


class NavigationFix(Coordinate):
    accuracy: float = Field(ge=0, le=10000, strict=True)
    timestamp: AwareDatetime


class NavigationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence: int = Field(ge=1, le=2147483647, strict=True)
    fix: NavigationFix
    navigation_token: str = Field(pattern=r"^[a-f0-9]{32}$")


class NavigationSession(BaseModel):
    journey_id: str
    route_version: str
    expires_at: AwareDatetime


class ProgressResult(BaseModel):
    accepted: bool
    alert: Literal["none", "sent", "failed", "suppressed"] = "none"
    arrived: bool = False
