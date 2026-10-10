from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response

from app.core.firebase import signed_in_uid
from app.schemas.navigation import (
    DeviceRegistration,
    NavigationSession,
    NavigationStart,
    NavigationUpdate,
    ProgressResult,
)
from app.services.notifications import NavigationService

router = APIRouter(prefix="/api", tags=["private navigation"])
UserId = Annotated[str, Depends(signed_in_uid)]
DeviceId = Annotated[str, Path(pattern=r"^[a-zA-Z0-9_-]{10,128}$")]
JourneyId = Annotated[str, Path(pattern=r"^[a-f0-9]{32}$")]


def service(request: Request):
    return NavigationService(request.app.state.firebase, request.app.state.navigation_routes)


@router.put("/me/devices/{device_id}", status_code=204)
def register(device_id: DeviceId, registration: DeviceRegistration, request: Request, uid: UserId):
    service(request).register(uid, device_id, registration)
    return Response(status_code=204)


@router.delete("/me/devices/{device_id}", status_code=204)
def unregister(device_id: DeviceId, request: Request, uid: UserId):
    service(request).unregister(uid, device_id)
    return Response(status_code=204)


@router.post("/navigation/sessions", response_model=NavigationSession)
def start(payload: NavigationStart, request: Request, uid: UserId):
    return service(request).start(uid, payload)


@router.post("/navigation/sessions/{journey_id}/progress", response_model=ProgressResult)
def progress(journey_id: JourneyId, payload: NavigationUpdate, request: Request, uid: UserId):
    return service(request).progress(uid, journey_id, payload)


@router.delete("/navigation/sessions/{journey_id}", status_code=204)
def stop(journey_id: JourneyId, request: Request, uid: UserId):
    service(request).stop(uid, journey_id)
    return Response(status_code=204)
