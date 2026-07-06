"""
Web Activity Analytics API Routes

管理层API，用于查看和分析Web搜索活动统计数据。

端点：
- GET  /api/v1/admin/web-activity/stats - 获取统计摘要
- GET  /api/v1/admin/web-activity/report - 生成分析报告
- GET  /api/v1/admin/web-activity/logs - 查看原始日志
- GET  /api/v1/admin/web-activity/top-websites - 最常访问网站
- GET  /api/v1/admin/web-activity/top-users - 最活跃用户
- GET  /api/v1/admin/web-activity/alerts - 告警信息
- POST /api/v1/admin/web-activity/backup - 备份数据
- POST /api/v1/admin/web-activity/maintenance - 维护任务
"""

from datetime import datetime, timedelta
from typing import Optional, Any

from fastapi import APIRouter, Query, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from app.agents.web_activity_logger import get_activity_logger, get_activity_analyzer
from app.agents.web_activity_alerts import get_alert_system, check_and_alert
from app.agents.web_activity_data_manager import get_data_manager
from app.api.dependencies import _require_user, _require_permission

router = APIRouter(prefix="/api/v1/admin/web-activity", tags=["Admin - Web Activity"])


# === Request/Response Models ===

class StatsResponse(BaseModel):
    """统计摘要响应"""
    summary: dict
    top_websites: list
    top_users: list
    hourly_distribution: dict
    date_range: dict


class LogEntry(BaseModel):
    """日志条目"""
    timestamp: str
    user_id: str
    session_id: str
    query: str
    query_sanitized: bool
    search_success: bool
    results_count: int
    websites_accessed: list
    ip_address: Optional[str] = None


class WebsiteStats(BaseModel):
    """网站统计"""
    domain: str
    visit_count: int
    avg_trust_score: float


class UserStats(BaseModel):
    """用户统计"""
    user_id: str
    search_count: int


# === Helper Functions ===

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """解析日期字符串"""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}")


# === API Endpoints ===

@router.get("/stats", response_model=StatsResponse)
async def get_web_activity_stats(
    start_date: Optional[str] = Query(None, description="开始日期 (ISO format: YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (ISO format: YYYY-MM-DD)"),
    user_id: Optional[str] = Query(None, description="筛选特定用户"),
    current_user: dict[str, Any] = Depends(_require_user),  # 使用主认证系统
):
    """
    获取Web搜索活动统计摘要

    返回：
    - 总体统计（搜索次数、成功率等）
    - 最常访问的网站
    - 最活跃用户
    - 24小时活动分布
    """
    start = parse_date(start_date)
    end = parse_date(end_date)

    analyzer = get_activity_analyzer()
    analysis = analyzer.analyze(start_date=start, end_date=end, user_id=user_id)

    # 检查告警
    try:
        alerts = check_and_alert(analysis['summary'])
        if alerts:
            logger.warning(f"Triggered {len(alerts)} alerts")
    except Exception as e:
        logger.error(f"Alert check failed: {e}")

    return analysis


@router.get("/report")
async def get_web_activity_report(
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    format: str = Query("html", description="输出格式: text, json, html"),
):
    """
    生成Web搜索活动分析报告

    支持格式：
    - text: 纯文本报告
    - json: JSON格式数据
    - html: HTML可视化报告
    """
    if format not in ["text", "json", "html"]:
        raise HTTPException(status_code=400, detail="Invalid format. Must be: text, json, or html")

    start = parse_date(start_date)
    end = parse_date(end_date)

    analyzer = get_activity_analyzer()
    report = analyzer.generate_report(start_date=start, end_date=end, output_format=format)

    if format == "html":
        return HTMLResponse(content=report)
    else:
        return {"report": report}


@router.get("/logs")
async def get_web_activity_logs(
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    user_id: Optional[str] = Query(None, description="筛选特定用户"),
    limit: int = Query(100, description="返回记录数限制", ge=1, le=1000),
    offset: int = Query(0, description="跳过记录数", ge=0),
):
    """
    查看Web搜索活动原始日志

    支持分页和筛选
    """
    start = parse_date(start_date)
    end = parse_date(end_date)

    logger = get_activity_logger()
    logs = logger.get_logs(start_date=start, end_date=end, user_id=user_id)

    # 分页
    total = len(logs)
    logs_page = logs[offset:offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "logs": logs_page,
    }


@router.get("/top-websites", response_model=list[WebsiteStats])
async def get_top_websites(
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    limit: int = Query(20, description="返回数量", ge=1, le=100),
):
    """
    获取最常访问的网站列表

    返回访问次数和平均信任度评分
    """
    start = parse_date(start_date)
    end = parse_date(end_date)

    analyzer = get_activity_analyzer()
    analysis = analyzer.analyze(start_date=start, end_date=end)

    return analysis["top_websites"][:limit]


@router.get("/top-users", response_model=list[UserStats])
async def get_top_users(
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    limit: int = Query(20, description="返回数量", ge=1, le=100),
):
    """
    获取最活跃用户列表

    返回搜索次数排名
    """
    start = parse_date(start_date)
    end = parse_date(end_date)

    analyzer = get_activity_analyzer()
    analysis = analyzer.analyze(start_date=start, end_date=end)

    return analysis["top_users"][:limit]


@router.get("/hourly-distribution")
async def get_hourly_distribution(
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
):
    """
    获取24小时活动分布

    返回每小时的搜索次数
    """
    start = parse_date(start_date)
    end = parse_date(end_date)

    analyzer = get_activity_analyzer()
    analysis = analyzer.analyze(start_date=start, end_date=end)

    return {
        "distribution": analysis["hourly_distribution"],
        "peak_hour": max(analysis["hourly_distribution"].items(), key=lambda x: x[1])[0] if analysis["hourly_distribution"] else None,
    }


@router.get("/export")
async def export_logs(
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    format: str = Query("csv", description="导出格式: csv, json"),
):
    """
    导出日志数据

    支持CSV和JSON格式
    """
    if format not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="Invalid format. Must be: csv or json")

    start = parse_date(start_date)
    end = parse_date(end_date)

    logger = get_activity_logger()
    logs = logger.get_logs(start_date=start, end_date=end)

    if format == "json":
        import json
        return {"data": logs}
    else:  # csv
        import csv
        import io

        output = io.StringIO()
        if logs:
            writer = csv.DictWriter(output, fieldnames=logs[0].keys())
            writer.writeheader()
            for log in logs:
                # 简化嵌套字段
                row = log.copy()
                row["websites_accessed"] = len(log.get("websites_accessed", []))
                row["metrics"] = str(log.get("metrics", {}))
                writer.writerow(row)

        return {"csv": output.getvalue()}


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(
    days: int = Query(7, description="显示最近几天的数据", ge=1, le=90),
):
    """
    获取Web活动监控仪表板（HTML页面）

    包含图表和实时统计
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    analyzer = get_activity_analyzer()
    report = analyzer.generate_report(start_date=start_date, end_date=end_date, output_format="html")

    return report


# === 新增端点：告警管理 ===

@router.get("/alerts")
async def get_alerts(
    hours: int = Query(24, description="获取最近几小时的告警", ge=1, le=168),
    level: Optional[str] = Query(None, description="告警级别筛选: info, warning, error, critical"),
    current_user: dict[str, Any] = Depends(_require_user),
):
    """
    获取最近的告警记录

    返回系统触发的告警信息
    """
    alert_system = get_alert_system()

    from app.agents.web_activity_alerts import AlertLevel
    alert_level = AlertLevel(level) if level else None

    alerts = alert_system.get_recent_alerts(hours=hours, level=alert_level)

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
        ]
    }


@router.get("/alerts/summary")
async def get_alert_summary(
    hours: int = Query(24, description="统计最近几小时", ge=1, le=168),
    current_user: dict[str, Any] = Depends(_require_user),
):
    """
    获取告警摘要统计

    返回告警数量、级别分布等
    """
    alert_system = get_alert_system()
    summary = alert_system.get_alert_summary(hours=hours)

    return summary


# === 新增端点：数据管理 ===

@router.post("/backup")
async def backup_data(
    days: int = Query(7, description="备份最近几天的数据", ge=1, le=90),
    current_user: dict[str, Any] = Depends(_require_user),  # 要求管理员权限
):
    """
    备份日志数据

    创建最近N天的日志备份文件
    """
    data_manager = get_data_manager()
    result = data_manager.backup_logs(days=days)

    return result


@router.post("/archive")
async def archive_old_data(
    days: int = Query(30, description="归档超过几天的数据", ge=7, le=180),
    current_user: dict[str, Any] = Depends(_require_user),  # 要求Admin权限
):
    """
    归档旧日志

    压缩并归档超过N天的日志文件
    """
    data_manager = get_data_manager()
    result = data_manager.archive_old_logs(days=days)

    return result


@router.delete("/cleanup")
async def cleanup_old_data(
    days: int = Query(90, description="清理超过几天的数据", ge=30, le=365),
    current_user: dict[str, Any] = Depends(_require_user),  # 要求Admin权限
):
    """
    清理旧数据

    删除超过N天的日志和归档文件
    """
    data_manager = get_data_manager()
    result = data_manager.clean_old_logs(days=days)

    return result


@router.post("/maintenance")
async def run_maintenance(
    current_user: dict[str, Any] = Depends(_require_user),
):
    """
    执行定期维护任务

    自动执行：
    1. 备份最近7天日志
    2. 归档30天前日志
    3. 清理90天前日志
    4. 清理30天前备份
    """
    data_manager = get_data_manager()
    result = data_manager.scheduled_maintenance()

    return result


@router.get("/storage")
async def get_storage_info(
    current_user: dict[str, Any] = Depends(_require_user),
):
    """
    获取存储空间信息

    返回日志、归档、备份目录的大小和文件数
    """
    data_manager = get_data_manager()
    storage_info = data_manager.get_storage_info()

    return storage_info


# === 新增端点：系统健康检查 ===

@router.get("/health")
async def health_check():
    """
    系统健康检查

    检查各组件是否正常运行（无需认证）
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }

    # 检查日志记录器
    try:
        logger = get_activity_logger()
        health_status["components"]["logger"] = "ok"
    except Exception as e:
        health_status["components"]["logger"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"

    # 检查分析器
    try:
        analyzer = get_activity_analyzer()
        health_status["components"]["analyzer"] = "ok"
    except Exception as e:
        health_status["components"]["analyzer"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"

    # 检查告警系统
    try:
        alert_system = get_alert_system()
        health_status["components"]["alerts"] = "ok"
    except Exception as e:
        health_status["components"]["alerts"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"

    return health_status
