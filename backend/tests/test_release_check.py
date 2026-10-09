import pytest
from test_comparison import request, snapshot, stations, walking

from app.model.baseline import BaselinePolicy
from app.services.comparison import compare_routes
from scripts.check_release import verify_mode


def replay():
    journey = request().model_copy(update={"snapshot_id": "synthetic-snapshot"})
    result = compare_routes(
        [walking(), walking(1300.0, identity="alternative")],
        journey,
        snapshot(stations()),
        BaselinePolicy(),
    )
    return journey, result


def test_release_rejects_wrong_snapshot_or_missing_replay_scores():
    journey, result = replay()
    verify_mode(journey, result)
    with pytest.raises(ValueError, match="snapshot"):
        verify_mode(journey.model_copy(update={"snapshot_id": "another"}), result)
    result.candidates[0].estimated_exposure = None
    with pytest.raises(ValueError, match="support"):
        verify_mode(journey, result)


def test_release_rejects_live_replay_substitution_and_unsupported_scores():
    journey, result = replay()
    journey = journey.model_copy(update={"data_mode": "live", "snapshot_id": None})
    with pytest.raises(ValueError, match="silently"):
        verify_mode(journey, result)
    result.data_quality.data_mode = "live"
    result.data_quality.station_count = 1
    with pytest.raises(ValueError, match="withhold"):
        verify_mode(journey, result)


def test_release_rejects_incorrect_budget_and_unvalidated_reduction():
    journey, result = replay()
    result.candidates[0].within_budget = False
    with pytest.raises(ValueError, match="eligibility"):
        verify_mode(journey, result)
    result.candidates[0].within_budget = True
    result.estimated_reduction_percent = 10
    with pytest.raises(ValueError, match="reduction"):
        verify_mode(journey, result)
