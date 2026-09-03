"""Web Activity Analytics admin API routes."""

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.api.dependencies import _require_user
from app.api.deps.auth import require_admin
from app.api.transport.errors import error_responses
from app.services.legacy_web_activity import (
    check_and_alert,
    get_activity_analyzer,
    get_activity_logger,
    get_alert_level,
    get_alert_system,
    get_data_manager,
)

logger = logging.getLogger(__name__)

# Every date parameter below goes through parse_date, which is
# datetime.fromisoformat -- so all of them accept the same thing, and saying so
# in one place is what keeps the two wordings from drifting apart again.
_START_DATE_DESC = "开始日期 (ISO format: YYYY-MM-DD)"
_END_DATE_DESC = "结束日期 (ISO format: YYYY-MM-DD)"
_USER_FILTER_DESC = "筛选特定用户"

router = APIRouter(
    prefix="/api/v1/admin/web-activity",
    tags=["Admin - Web Activity"],
    dependencies=[Depends(require_admin)],
)


class StatsResponse(BaseModel):
    summary: dict
    top_websites: list
    top_users: list
    hourly_distribution: dict
    date_range: dict


class LogEntry(BaseModel):
    timestamp: str
    user_id: str
    session_id: str
    query: str
    query_sanitized: bool
    search_success: bool
    results_count: int
    websites_accessed: list
    ip_address: str | None = None


class WebsiteStats(BaseModel):
    domain: str
    visit_count: int
    avg_trust_score: float


class UserStats(BaseModel):
    user_id: str
    search_count: int


def parse_date(date_str: str | None) -> datetime | None:
    """Parse an ISO date, or reject it.

    Raises 400, which is why every route below that calls this declares it:
    the failure belongs to the endpoint a client called, not to the helper.
    """

    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}")


@router.get("/stats", response_model=StatsResponse, responses=error_responses(400))
async def get_web_activity_stats(
    start_date: str | None = Query(None, description=_START_DATE_DESC),
    end_date: str | None = Query(None, description=_END_DATE_DESC),
    user_id: str | None = Query(None, description=_USER_FILTER_DESC),
    current_user: dict[str, Any] = Depends(_require_user),
):
    start = parse_date(start_date)
    end = parse_date(end_date)
    analyzer = get_activity_analyzer()
    analysis = analyzer.analyze(start_date=start, end_date=end, user_id=user_id)
    try:
        alerts = check_and_alert(analysis["summary"])
        if alerts:
            logger.warning(f"Triggered {len(alerts)} alerts")
    except Exception:
        logger.exception("Alert check failed")
    return analysis


@router.get("/report", responses=error_responses(400))
async def get_web_activity_report(
    start_date: str | None = Query(None, description=_START_DATE_DESC),
    end_date: str | None = Query(None, description=_END_DATE_DESC),
    format: str = Query("html", description="输出格式: text, json, html"),
):
    if format not in ["text", "json", "html"]:
        raise HTTPException(status_code=400, detail="Invalid format. Must be: text, json, or html")
    start = parse_date(start_date)
    end = parse_date(end_date)
    report = get_activity_analyzer().generate_report(start_date=start, end_date=end, output_format=format)
    if format == "html":
        return HTMLResponse(content=report)
    return {"report": report}


@router.get("/logs", responses=error_responses(400))
async def get_web_activity_logs(
    start_date: str | None = Query(None, description=_START_DATE_DESC),
    end_date: str | None = Query(None, description=_END_DATE_DESC),
    user_id: str | None = Query(None, description=_USER_FILTER_DESC),
    limit: int = Query(100, description="返回记录数限制", ge=1, le=1000),
    offset: int = Query(0, description="跳过记录数", ge=0),
):
    start = parse_date(start_date)
    end = parse_date(end_date)
    logs = get_activity_logger().get_logs(start_date=start, end_date=end, user_id=user_id)
    return {"total": len(logs), "offset": offset, "limit": limit, "logs": logs[offset : offset + limit]}


@router.get("/top-websites", response_model=list[WebsiteStats], responses=error_responses(400))
async def get_top_websites(
    start_date: str | None = Query(None, description=_START_DATE_DESC),
    end_date: str | None = Query(None, description=_END_DATE_DESC),
    limit: int = Query(20, description="返回数量", ge=1, le=100),
):
    analysis = get_activity_analyzer().analyze(start_date=parse_date(start_date), end_date=parse_date(end_date))
    return analysis["top_websites"][:limit]


@router.get("/top-users", response_model=list[UserStats], responses=error_responses(400))
async def get_top_users(
    start_date: str | None = Query(None, description=_START_DATE_DESC),
    end_date: str | None = Query(None, description=_END_DATE_DESC),
    limit: int = Query(20, description="返回数量", ge=1, le=100),
):
    analysis = get_activity_analyzer().analyze(start_date=parse_date(start_date), end_date=parse_date(end_date))
    return analysis["top_users"][:limit]


@router.get("/hourly-distribution", responses=error_responses(400))
async def get_hourly_distribution(
    start_date: str | None = Query(None, description=_START_DATE_DESC),
    end_date: str | None = Query(None, description=_END_DATE_DESC),
):
    analysis = get_activity_analyzer().analyze(start_date=parse_date(start_date), end_date=parse_date(end_date))
    distribution = analysis["hourly_distribution"]
    return {
        "distribution": distribution,
        "peak_hour": max(distribution.items(), key=lambda x: x[1])[0] if distribution else None,
    }


@router.get("/export", responses=error_responses(400))
async def export_logs(
    start_date: str | None = Query(None, description=_START_DATE_DESC),
    end_date: str | None = Query(None, description=_END_DATE_DESC),
    format: str = Query("csv", description="导出格式: csv, json"),
):
    if format not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="Invalid format. Must be: csv or json")
    logs = get_activity_logger().get_logs(start_date=parse_date(start_date), end_date=parse_date(end_date))
    if format == "json":
        return {"data": logs}
    import csv
    import io

    output = io.StringIO()
    if logs:
        writer = csv.DictWriter(output, fieldnames=logs[0].keys())
        writer.writeheader()
        for log in logs:
            row = log.copy()
            row["websites_accessed"] = len(log.get("websites_accessed", []))
            row["metrics"] = str(log.get("metrics", {}))
            writer.writerow(row)
    return {"csv": output.getvalue()}


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(days: int = Query(7, description="显示最近几天的数据", ge=1, le=90)):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    return get_activity_analyzer().generate_report(start_date=start_date, end_date=end_date, output_format="html")


@router.get("/alerts")
async def get_alerts(
    hours: int = Query(24, description="获取最近几小时的告警", ge=1, le=168),
    level: str | None = Query(None, description="告警级别筛选: info, warning, error, critical"),
    current_user: dict[str, Any] = Depends(_require_user),
):
    alerts = get_alert_system().get_recent_alerts(hours=hours, level=get_alert_level(level) if level else None)
    return {
        "total": len(alerts),
        "alerts": [
            {
                "timestamp": alert.timestamp.isoformat(),
                "rule_name": alert.rule_name,
                "level": alert.level.value,
                "message": alert.message,
                "metric_value": alert.metric_value,
                "threshold": alert.threshold,
            }
            for alert in alerts
        ],
    }


@router.get("/alerts/summary")
async def get_alert_summary(
    hours: int = Query(24, description="统计最近几小时", ge=1, le=168),
    current_user: dict[str, Any] = Depends(_require_user),
):
    return get_alert_system().get_alert_summary(hours=hours)


@router.post("/backup")
async def backup_data(
    days: int = Query(7, description="备份最近几天的数据", ge=1, le=90),
    current_user: dict[str, Any] = Depends(_require_user),
):
    return get_data_manager().backup_logs(days=days)


@router.post("/archive")
async def archive_old_data(
    days: int = Query(30, description="归档超过几天的数据", ge=7, le=180),
    current_user: dict[str, Any] = Depends(_require_user),
):
    return get_data_manager().archive_old_logs(days=days)


@router.delete("/cleanup")
async def cleanup_old_data(
    days: int = Query(90, description="清理超过几天的数据", ge=30, le=365),
    current_user: dict[str, Any] = Depends(_require_user),
):
    return get_data_manager().clean_old_logs(days=days)


@router.post("/maintenance")
async def run_maintenance(current_user: dict[str, Any] = Depends(_require_user)):
    return get_data_manager().scheduled_maintenance()


@router.get("/storage")
async def get_storage_info(current_user: dict[str, Any] = Depends(_require_user)):
    return get_data_manager().get_storage_info()


@router.get("/health")
async def health_check():
    health_status = {"status": "healthy", "timestamp": datetime.now().isoformat(), "components": {}}
    try:
        get_activity_logger()
        health_status["components"]["logger"] = "ok"
    except Exception as e:
        health_status["components"]["logger"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    try:
        get_activity_analyzer()
        health_status["components"]["analyzer"] = "ok"
    except Exception as e:
        health_status["components"]["analyzer"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    try:
        get_alert_system()
        health_status["components"]["alerts"] = "ok"
    except Exception as e:
        health_status["components"]["alerts"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    return health_status
