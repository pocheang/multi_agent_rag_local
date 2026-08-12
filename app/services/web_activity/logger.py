"""
Web Research Activity Logger

记录和追踪用户的Web搜索活动，供管理层监控和分析。

功能：
- 记录每次Web搜索的详细信息
- 追踪访问的网站域名
- 用户行为统计
- 时间序列分析
- 支持导出和报告生成
"""

import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from collections import Counter, defaultdict

logger = logging.getLogger("app.agents.web_activity_logger")


class WebActivityLogger:
    """
    Web搜索活动日志记录器

    记录内容：
    - 用户ID和查询内容
    - 访问的网站列表
    - 搜索时间和结果数量
    - 敏感信息脱敏标记
    """

    def __init__(self, log_dir: str = "logs/web_activity"):
        """
        初始化日志记录器

        Args:
            log_dir: 日志文件存储目录
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 当前日志文件路径
        self.current_log_file = self.log_dir / f"web_activity_{datetime.now().strftime('%Y%m%d')}.jsonl"

        logger.info(f"WebActivityLogger initialized with log_dir: {self.log_dir}")

    def log_search(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        query: str = "",
        query_sanitized: bool = False,
        result: Dict = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """
        记录一次Web搜索活动

        Args:
            user_id: 用户ID
            session_id: 会话ID
            query: 查询内容（已脱敏）
            query_sanitized: 是否进行了脱敏
            result: 搜索结果
            ip_address: 用户IP地址
            user_agent: 用户浏览器信息
        """
        if result is None:
            result = {}

        # 提取访问的网站域名
        websites = []
        for citation in result.get("citations", []):
            source = citation.get("source", "")
            if source.startswith("http"):
                from urllib.parse import urlparse
                domain = urlparse(source).netloc
                websites.append({
                    "domain": domain,
                    "url": source,
                    "score": citation.get("metadata", {}).get("source_score", 0.0),
                })

        # 构建日志记录
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id or "anonymous",
            "session_id": session_id or "unknown",
            "query": query[:200],  # 限制长度
            "query_sanitized": query_sanitized,
            "search_success": result.get("used", False),
            "results_count": len(result.get("citations", [])),
            "websites_accessed": websites,
            "metrics": result.get("metrics", {}),
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        # 写入日志文件
        try:
            with open(self.current_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            logger.debug(f"Logged web search activity for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to write activity log: {e}")

    def get_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        读取日志记录

        Args:
            start_date: 开始日期
            end_date: 结束日期
            user_id: 用户ID筛选

        Returns:
            日志记录列表
        """
        logs = []

        # 如果没有指定日期范围，读取最近7天
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)
        if not end_date:
            end_date = datetime.now()

        # 遍历日期范围内的所有日志文件
        current = start_date
        while current <= end_date:
            log_file = self.log_dir / f"web_activity_{current.strftime('%Y%m%d')}.jsonl"
            if log_file.exists():
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                entry = json.loads(line)

                                # 时间过滤
                                entry_time = datetime.fromisoformat(entry["timestamp"])
                                if entry_time < start_date or entry_time > end_date:
                                    continue

                                # 用户过滤
                                if user_id and entry.get("user_id") != user_id:
                                    continue

                                logs.append(entry)
                except Exception as e:
                    logger.error(f"Failed to read log file {log_file}: {e}")

            current += timedelta(days=1)

        return logs


class WebActivityAnalyzer:
    """
    Web搜索活动分析器

    提供统计和分析功能：
    - 最常访问的网站
    - 用户搜索行为分析
    - 时间分布统计
    - 搜索成功率
    """

    def __init__(self, logger: WebActivityLogger):
        """
        初始化分析器

        Args:
            logger: WebActivityLogger实例
        """
        self.logger = logger

    def analyze(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """
        分析Web搜索活动

        Args:
            start_date: 开始日期
            end_date: 结束日期
            user_id: 用户ID筛选

        Returns:
            分析结果字典
        """
        logs = self.logger.get_logs(start_date, end_date, user_id)

        if not logs:
            return {
                "total_searches": 0,
                "message": "No data available for the specified period"
            }

        # 统计指标
        total_searches = len(logs)
        successful_searches = sum(1 for log in logs if log.get("search_success"))
        sanitized_queries = sum(1 for log in logs if log.get("query_sanitized"))

        # 网站统计
        website_counter = Counter()
        website_scores = defaultdict(list)

        for log in logs:
            for website in log.get("websites_accessed", []):
                domain = website.get("domain", "")
                if domain:
                    website_counter[domain] += 1
                    website_scores[domain].append(website.get("score", 0.0))

        # 计算平均评分
        top_websites = []
        for domain, count in website_counter.most_common(20):
            avg_score = sum(website_scores[domain]) / len(website_scores[domain])
            top_websites.append({
                "domain": domain,
                "visit_count": count,
                "avg_trust_score": round(avg_score, 2),
            })

        # 用户统计
        user_counter = Counter(log.get("user_id", "anonymous") for log in logs)
        top_users = [
            {"user_id": user, "search_count": count}
            for user, count in user_counter.most_common(10)
        ]

        # 时间分布
        hour_distribution = Counter()
        for log in logs:
            timestamp = datetime.fromisoformat(log["timestamp"])
            hour_distribution[timestamp.hour] += 1

        # 查询统计
        queries = [log.get("query", "") for log in logs]
        avg_query_length = sum(len(q) for q in queries) / len(queries) if queries else 0

        # 性能统计
        search_times = []
        for log in logs:
            metrics = log.get("metrics", {})
            search_time = metrics.get("search_time", 0.0)
            if search_time > 0:
                search_times.append(search_time)

        avg_search_time = sum(search_times) / len(search_times) if search_times else 0

        return {
            "summary": {
                "total_searches": total_searches,
                "successful_searches": successful_searches,
                "success_rate": round(successful_searches / total_searches * 100, 2) if total_searches > 0 else 0,
                "sanitized_queries": sanitized_queries,
                "unique_users": len(user_counter),
                "unique_websites": len(website_counter),
                "avg_query_length": round(avg_query_length, 1),
                "avg_search_time": round(avg_search_time, 2),
            },
            "top_websites": top_websites,
            "top_users": top_users,
            "hourly_distribution": dict(sorted(hour_distribution.items())),
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        }

    def generate_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        output_format: str = "text",
    ) -> str:
        """
        生成分析报告

        Args:
            start_date: 开始日期
            end_date: 结束日期
            output_format: 输出格式 (text/json/html)

        Returns:
            报告内容
        """
        analysis = self.analyze(start_date, end_date)

        if output_format == "json":
            return json.dumps(analysis, indent=2, ensure_ascii=False)

        elif output_format == "html":
            return self._generate_html_report(analysis)

        else:  # text
            return self._generate_text_report(analysis)

    def _generate_text_report(self, analysis: Dict) -> str:
        """生成文本格式报告"""
        summary = analysis["summary"]

        report = []
        report.append("=" * 60)
        report.append("Web搜索活动分析报告")
        report.append("=" * 60)
        report.append("")

        report.append("📊 总体统计")
        report.append("-" * 60)
        report.append(f"总搜索次数: {summary['total_searches']}")
        report.append(f"成功搜索: {summary['successful_searches']} ({summary['success_rate']}%)")
        report.append(f"脱敏查询: {summary['sanitized_queries']}")
        report.append(f"独立用户: {summary['unique_users']}")
        report.append(f"访问网站: {summary['unique_websites']}")
        report.append(f"平均查询长度: {summary['avg_query_length']} 字符")
        report.append(f"平均搜索耗时: {summary['avg_search_time']} 秒")
        report.append("")

        report.append("🌐 最常访问的网站 (Top 10)")
        report.append("-" * 60)
        for i, website in enumerate(analysis["top_websites"][:10], 1):
            report.append(
                f"{i:2d}. {website['domain']:40s} "
                f"访问次数: {website['visit_count']:4d} "
                f"信任度: {website['avg_trust_score']:.2f}"
            )
        report.append("")

        report.append("👥 最活跃用户 (Top 10)")
        report.append("-" * 60)
        for i, user in enumerate(analysis["top_users"][:10], 1):
            report.append(f"{i:2d}. {user['user_id']:30s} 搜索次数: {user['search_count']:4d}")
        report.append("")

        report.append("🕐 时间分布 (24小时)")
        report.append("-" * 60)
        hour_dist = analysis["hourly_distribution"]
        for hour in range(24):
            count = hour_dist.get(hour, 0)
            bar = "█" * (count // 5) if count > 0 else ""
            report.append(f"{hour:02d}:00 | {bar} {count}")
        report.append("")

        report.append("=" * 60)

        return "\n".join(report)

    def _generate_html_report(self, analysis: Dict) -> str:
        """生成HTML格式报告"""
        summary = analysis["summary"]

        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web搜索活动分析报告</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-left: 4px solid #3498db;
            padding-left: 10px;
        }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #3498db;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .bar-chart {{
            margin: 20px 0;
        }}
        .bar {{
            display: flex;
            align-items: center;
            margin: 5px 0;
        }}
        .bar-label {{
            width: 60px;
            font-size: 0.9em;
        }}
        .bar-fill {{
            height: 25px;
            background: linear-gradient(to right, #3498db, #2ecc71);
            border-radius: 4px;
            display: flex;
            align-items: center;
            padding: 0 10px;
            color: white;
            font-size: 0.85em;
        }}
        .trust-score {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9em;
            font-weight: bold;
        }}
        .trust-high {{ background: #2ecc71; color: white; }}
        .trust-medium {{ background: #f39c12; color: white; }}
        .trust-low {{ background: #e74c3c; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Web搜索活动分析报告</h1>

        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-label">总搜索次数</div>
                <div class="stat-value">{summary['total_searches']}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">成功率</div>
                <div class="stat-value">{summary['success_rate']}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">独立用户</div>
                <div class="stat-value">{summary['unique_users']}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">访问网站</div>
                <div class="stat-value">{summary['unique_websites']}</div>
            </div>
        </div>

        <h2>🌐 最常访问的网站</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>网站域名</th>
                    <th>访问次数</th>
                    <th>信任度评分</th>
                </tr>
            </thead>
            <tbody>
"""

        for i, website in enumerate(analysis["top_websites"][:15], 1):
            score = website['avg_trust_score']
            if score >= 0.7:
                score_class = "trust-high"
            elif score >= 0.5:
                score_class = "trust-medium"
            else:
                score_class = "trust-low"

            html += f"""
                <tr>
                    <td>{i}</td>
                    <td>{website['domain']}</td>
                    <td>{website['visit_count']}</td>
                    <td><span class="trust-score {score_class}">{score:.2f}</span></td>
                </tr>
"""

        html += """
            </tbody>
        </table>

        <h2>👥 最活跃用户</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>用户ID</th>
                    <th>搜索次数</th>
                </tr>
            </thead>
            <tbody>
"""

        for i, user in enumerate(analysis["top_users"][:10], 1):
            html += f"""
                <tr>
                    <td>{i}</td>
                    <td>{user['user_id']}</td>
                    <td>{user['search_count']}</td>
                </tr>
"""

        html += """
            </tbody>
        </table>

        <h2>🕐 24小时活动分布</h2>
        <div class="bar-chart">
"""

        hour_dist = analysis["hourly_distribution"]
        max_count = max(hour_dist.values()) if hour_dist else 1

        for hour in range(24):
            count = hour_dist.get(hour, 0)
            width = (count / max_count * 100) if max_count > 0 else 0
            html += f"""
            <div class="bar">
                <div class="bar-label">{hour:02d}:00</div>
                <div class="bar-fill" style="width: {width}%">{count}</div>
            </div>
"""

        html += """
        </div>
    </div>
</body>
</html>
"""

        return html


# 全局实例
_global_activity_logger = None
_global_activity_analyzer = None


def get_activity_logger() -> WebActivityLogger:
    """获取全局日志记录器实例"""
    global _global_activity_logger
    if _global_activity_logger is None:
        _global_activity_logger = WebActivityLogger()
    return _global_activity_logger


def get_activity_analyzer() -> WebActivityAnalyzer:
    """获取全局分析器实例"""
    global _global_activity_analyzer
    if _global_activity_analyzer is None:
        _global_activity_analyzer = WebActivityAnalyzer(get_activity_logger())
    return _global_activity_analyzer
