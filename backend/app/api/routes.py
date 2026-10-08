from fastapi import APIRouter, HTTPException

from app.schemas.routes import ComparisonRequest, ComparisonResponse, PilotResponse

router = APIRouter(prefix="/api")


@router.get("/pilot", response_model=PilotResponse)
def pilot() -> PilotResponse:
    return PilotResponse()


@router.post(
    "/routes/compare",
    response_model=ComparisonResponse,
    responses={503: {"description": "Routing and exposure scoring are not implemented yet"}},
)
def compare(request: ComparisonRequest) -> ComparisonResponse:
    # Request validation works now. Provider calls and scoring belong to the next build step.
    raise HTTPException(
        status_code=503,
        detail={
            "code": "comparison_not_ready",
            "message": "Route comparison is not available yet. Routing and data checks are next.",
        },
    )
