"""Versioned routing/comparison cache. Hits always re-score current observation support."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.config import Settings
from app.model.baseline import BaselinePolicy
from app.schemas.routes import ComparisonRequest, ComparisonResponse
from app.services.snapshots import CA, PollutionSnapshot
from app.services.walking import WalkingRoute

CONTRACT = "walking-steps-v1"


def cache_identity(
    request: ComparisonRequest, snapshot: PollutionSnapshot, policy: BaselinePolicy, now: datetime
) -> tuple[str, datetime]:
    bucket = datetime.fromtimestamp(int(now.timestamp()) // 300 * 300, UTC)
    identity = {
        **request.model_dump(exclude={"snapshot_id"}),
        "snapshot_id": snapshot.snapshot_id,
        "data_version": snapshot.data_version,
        "model_version": policy.version,
        "bucket": bucket.isoformat(),
        "contract": CONTRACT,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    return digest, bucket


def read_routes(
    settings: Settings,
    request: ComparisonRequest,
    snapshot: PollutionSnapshot,
    policy: BaselinePolicy,
    now: datetime,
) -> list[WalkingRoute] | None:
    if settings.database_url is None:
        return None
    key, _ = cache_identity(request, snapshot, policy, now)
    try:
        with psycopg.connect(
            settings.database_url.get_secret_value(),
            connect_timeout=3,
            sslmode="verify-full",
            sslrootcert=str(CA),
            row_factory=dict_row,
        ) as conn:
            conn.read_only = True
            conn.execute("SET LOCAL statement_timeout = 3000")
            row = conn.execute(
                "SELECT response FROM aeroroute.route_comparison_cache "
                "WHERE cache_key=%s AND snapshot_id=%s AND data_version=%s "
                "AND model_version=%s AND expires_at>%s",
                (key, snapshot.snapshot_id, snapshot.data_version, policy.version, now),
            ).fetchone()
        if row is None or row["response"].get("contract") != CONTRACT:
            return None
        routes = row["response"]["walking_routes"]
        if not isinstance(routes, list) or not 1 <= len(routes) <= 3:
            return None
        return [WalkingRoute.model_validate(route) for route in routes]
    except (psycopg.Error, ValueError, KeyError, TypeError, AttributeError):
        return None  # Optional cache failure must not prevent a genuine provider request.


def store_routes(
    settings: Settings,
    request: ComparisonRequest,
    snapshot: PollutionSnapshot,
    policy: BaselinePolicy,
    routes: list[WalkingRoute],
    response: ComparisonResponse,
    now: datetime,
) -> None:
    if settings.database_url is None or not routes:
        return
    key, bucket = cache_identity(request, snapshot, policy, now)
    payload = {
        "contract": CONTRACT,
        "walking_routes": [route.model_dump(mode="json") for route in routes],
        "comparison": response.model_dump(mode="json"),
    }
    try:
        with psycopg.connect(
            settings.database_url.get_secret_value(),
            connect_timeout=3,
            sslmode="verify-full",
            sslrootcert=str(CA),
        ) as conn:
            conn.execute("SET LOCAL statement_timeout = 3000")
            conn.execute(
                "DELETE FROM aeroroute.route_comparison_cache WHERE expires_at<=%s", (now,)
            )
            conn.execute(
                "INSERT INTO aeroroute.route_comparison_cache "
                "(cache_key,origin_latitude,origin_longitude,destination_latitude,"
                "destination_longitude,mode,time_bucket,max_detour_minutes,snapshot_id,"
                "data_version,model_version,response,created_at,expires_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(cache_key) DO UPDATE SET response=EXCLUDED.response,"
                "created_at=EXCLUDED.created_at,expires_at=EXCLUDED.expires_at",
                (
                    key,
                    request.origin.lat,
                    request.origin.lng,
                    request.destination.lat,
                    request.destination.lng,
                    request.mode,
                    bucket,
                    request.max_detour_minutes,
                    snapshot.snapshot_id,
                    snapshot.data_version,
                    policy.version,
                    Jsonb(payload),
                    now,
                    now + timedelta(seconds=settings.cache_ttl_seconds),
                ),
            )
    except psycopg.Error:
        return
