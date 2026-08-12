"""Lazy adapters for legacy web-activity administration components."""

from __future__ import annotations

from typing import Any


def get_activity_logger() -> Any:
    """Return the legacy web-activity logger singleton."""
    from app.services.web_activity.logger import get_activity_logger as get_legacy_activity_logger

    return get_legacy_activity_logger()


def get_activity_analyzer() -> Any:
    """Return the legacy web-activity analyzer singleton."""
    from app.services.web_activity.logger import get_activity_analyzer as get_legacy_activity_analyzer

    return get_legacy_activity_analyzer()


def get_alert_system() -> Any:
    """Return the legacy web-activity alert system singleton."""
    from app.services.web_activity.alerts import get_alert_system as get_legacy_alert_system

    return get_legacy_alert_system()


def check_and_alert(summary: dict[str, Any]) -> Any:
    """Delegate legacy alert evaluation for an activity summary."""
    from app.services.web_activity.alerts import check_and_alert as check_legacy_alerts

    return check_legacy_alerts(summary)


def get_alert_level(level: str) -> Any:
    """Create the legacy alert-level value used by alert filtering."""
    from app.services.web_activity.alerts import AlertLevel

    return AlertLevel(level)


def get_data_manager() -> Any:
    """Return the legacy web-activity data manager singleton."""
    from app.services.web_activity.data_manager import get_data_manager as get_legacy_data_manager

    return get_legacy_data_manager()
