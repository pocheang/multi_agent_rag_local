"""
Web Activity Alert System

实时监控和告警系统，当检测到异常时自动发送通知。

功能：
- 实时阈值监控
- 多渠道告警（Email、Webhook、日志）
- 告警规则配置
- 告警历史记录
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass
import json
from pathlib import Path

logger = logging.getLogger("app.agents.web_activity_alerts")


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """告警渠道"""
    LOG = "log"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    description: str
    metric: str
    operator: str  # >, <, >=, <=, ==, !=
    threshold: float
    level: AlertLevel
    enabled: bool = True


@dataclass
class Alert:
    """告警记录"""
    timestamp: datetime
    rule_name: str
    level: AlertLevel
    message: str
    metric_value: float
    threshold: float
    metadata: Dict = None


class WebActivityAlertSystem:
    """
    Web活动告警系统

    监控指标：
    - 搜索成功率
    - 平均响应时间
    - 过滤率
    - 敏感查询数量
    - 异常访问模式
    """

    def __init__(self, config_path: str = "config/alert_config.json"):
        """
        初始化告警系统

        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.rules: List[AlertRule] = []
        self.alert_history: List[Alert] = []
        self.alert_channels: List[AlertChannel] = [AlertChannel.LOG]

        # 默认规则
        self._init_default_rules()

        # 加载配置
        self._load_config()

        logger.info(f"WebActivityAlertSystem initialized with {len(self.rules)} rules")

    def _init_default_rules(self):
        """初始化默认告警规则"""
        self.rules = [
            AlertRule(
                name="low_success_rate",
                description="搜索成功率过低",
                metric="success_rate",
                operator="<",
                threshold=80.0,
                level=AlertLevel.WARNING
            ),
            AlertRule(
                name="critical_success_rate",
                description="搜索成功率严重过低",
                metric="success_rate",
                operator="<",
                threshold=50.0,
                level=AlertLevel.CRITICAL
            ),
            AlertRule(
                name="high_response_time",
                description="平均响应时间过长",
                metric="avg_search_time",
                operator=">",
                threshold=5.0,
                level=AlertLevel.WARNING
            ),
            AlertRule(
                name="high_filter_rate",
                description="结果过滤率过高",
                metric="filter_rate",
                operator=">",
                threshold=80.0,
                level=AlertLevel.WARNING
            ),
            AlertRule(
                name="many_sanitized_queries",
                description="大量敏感查询被脱敏",
                metric="sanitized_queries",
                operator=">",
                threshold=10,
                level=AlertLevel.WARNING
            ),
            AlertRule(
                name="no_activity",
                description="长时间无搜索活动",
                metric="total_searches",
                operator="==",
                threshold=0,
                level=AlertLevel.INFO
            ),
        ]

    def _load_config(self):
        """从配置文件加载规则"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # 加载告警渠道
                if 'channels' in config:
                    self.alert_channels = [
                        AlertChannel(ch) for ch in config['channels']
                    ]

                # 加载自定义规则
                if 'rules' in config:
                    for rule_data in config['rules']:
                        rule = AlertRule(
                            name=rule_data['name'],
                            description=rule_data['description'],
                            metric=rule_data['metric'],
                            operator=rule_data['operator'],
                            threshold=float(rule_data['threshold']),
                            level=AlertLevel(rule_data['level']),
                            enabled=rule_data.get('enabled', True)
                        )
                        # 更新或添加规则
                        existing = next((r for r in self.rules if r.name == rule.name), None)
                        if existing:
                            self.rules.remove(existing)
                        self.rules.append(rule)

                logger.info(f"Loaded alert config from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load alert config: {e}")

    def check_metrics(self, metrics: Dict) -> List[Alert]:
        """
        检查指标并生成告警

        Args:
            metrics: 统计指标字典

        Returns:
            触发的告警列表
        """
        alerts = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            metric_value = metrics.get(rule.metric)
            if metric_value is None:
                continue

            # 评估规则
            triggered = self._evaluate_rule(rule, metric_value)

            if triggered:
                alert = Alert(
                    timestamp=datetime.now(),
                    rule_name=rule.name,
                    level=rule.level,
                    message=f"{rule.description}: {rule.metric}={metric_value} {rule.operator} {rule.threshold}",
                    metric_value=metric_value,
                    threshold=rule.threshold,
                    metadata=metrics
                )
                alerts.append(alert)
                self.alert_history.append(alert)

                # 发送告警
                self._send_alert(alert)

        return alerts

    def _evaluate_rule(self, rule: AlertRule, value: float) -> bool:
        """评估规则是否触发"""
        operators = {
            '>': lambda v, t: v > t,
            '<': lambda v, t: v < t,
            '>=': lambda v, t: v >= t,
            '<=': lambda v, t: v <= t,
            '==': lambda v, t: v == t,
            '!=': lambda v, t: v != t,
        }

        op_func = operators.get(rule.operator)
        if op_func:
            return op_func(value, rule.threshold)

        return False

    def _send_alert(self, alert: Alert):
        """发送告警到各个渠道"""
        for channel in self.alert_channels:
            try:
                if channel == AlertChannel.LOG:
                    self._send_log_alert(alert)
                elif channel == AlertChannel.EMAIL:
                    self._send_email_alert(alert)
                elif channel == AlertChannel.WEBHOOK:
                    self._send_webhook_alert(alert)
                elif channel == AlertChannel.SLACK:
                    self._send_slack_alert(alert)
            except Exception as e:
                logger.error(f"Failed to send alert via {channel}: {e}")

    def _send_log_alert(self, alert: Alert):
        """通过日志发送告警"""
        level_map = {
            AlertLevel.INFO: logger.info,
            AlertLevel.WARNING: logger.warning,
            AlertLevel.ERROR: logger.error,
            AlertLevel.CRITICAL: logger.critical,
        }

        log_func = level_map.get(alert.level, logger.info)
        log_func(f"[ALERT] {alert.rule_name}: {alert.message}")

    def _send_email_alert(self, alert: Alert):
        """通过Email发送告警"""
        # TODO: 实现Email发送
        # 需要配置SMTP服务器
        logger.debug(f"Email alert: {alert.message}")

    def _send_webhook_alert(self, alert: Alert):
        """通过Webhook发送告警"""
        # TODO: 实现Webhook发送
        # POST告警数据到配置的URL
        logger.debug(f"Webhook alert: {alert.message}")

    def _send_slack_alert(self, alert: Alert):
        """通过Slack发送告警"""
        # TODO: 实现Slack通知
        # 使用Slack Webhook
        logger.debug(f"Slack alert: {alert.message}")

    def get_recent_alerts(self, hours: int = 24, level: Optional[AlertLevel] = None) -> List[Alert]:
        """
        获取最近的告警

        Args:
            hours: 最近几小时
            level: 告警级别筛选

        Returns:
            告警列表
        """
        cutoff = datetime.now() - timedelta(hours=hours)

        alerts = [
            alert for alert in self.alert_history
            if alert.timestamp >= cutoff
        ]

        if level:
            alerts = [a for a in alerts if a.level == level]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_alert_summary(self, hours: int = 24) -> Dict:
        """
        获取告警摘要

        Args:
            hours: 统计最近几小时

        Returns:
            告警摘要字典
        """
        recent_alerts = self.get_recent_alerts(hours=hours)

        # 按级别统计
        by_level = {}
        for level in AlertLevel:
            by_level[level.value] = len([a for a in recent_alerts if a.level == level])

        # 按规则统计
        by_rule = {}
        for alert in recent_alerts:
            by_rule[alert.rule_name] = by_rule.get(alert.rule_name, 0) + 1

        return {
            "total_alerts": len(recent_alerts),
            "by_level": by_level,
            "by_rule": by_rule,
            "latest_alert": recent_alerts[0].message if recent_alerts else None,
        }


# 全局实例
_global_alert_system = None


def get_alert_system() -> WebActivityAlertSystem:
    """获取全局告警系统实例"""
    global _global_alert_system
    if _global_alert_system is None:
        _global_alert_system = WebActivityAlertSystem()
    return _global_alert_system


def check_and_alert(metrics: Dict) -> List[Alert]:
    """
    便捷函数：检查指标并发送告警

    Args:
        metrics: 统计指标

    Returns:
        触发的告警列表
    """
    alert_system = get_alert_system()
    return alert_system.check_metrics(metrics)
