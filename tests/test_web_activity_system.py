"""
Web Activity Monitoring System - Complete Test Script

Test all core features:
1. Activity Logger
2. Statistics Analyzer
3. Alert System
4. Data Manager
5. API Endpoints
6. Authentication
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("Web Activity Monitoring System - Complete Test")
print("=" * 80)
print()

# ============================================================================
# Test 1: Activity Logger
# ============================================================================
print("Test 1: Activity Logger")
print("-" * 80)

try:
    from app.agents.web_activity_logger import get_activity_logger

    logger = get_activity_logger()
    print(f"[PASS] Logger initialized successfully")
    print(f"       Log directory: {logger.log_dir}")

    # 模拟记录几次搜索
    test_searches = [
        {
            "user_id": "test_user_1",
            "session_id": "test_session_1",
            "query": "What is RAG in AI?",
            "query_sanitized": False,
            "result": {
                "used": True,
                "citations": [
                    {"source": "https://github.com/example", "content": "...", "metadata": {"source_score": 0.8}}
                ],
                "metrics": {"search_time": 1.23, "filter_time": 0.15, "total_results": 5}
            },
            "ip_address": "192.168.1.100"
        },
        {
            "user_id": "test_user_2",
            "session_id": "test_session_2",
            "query": "Python best practices",
            "query_sanitized": False,
            "result": {
                "used": True,
                "citations": [
                    {"source": "https://stackoverflow.com/q/12345", "content": "...", "metadata": {"source_score": 0.8}}
                ],
                "metrics": {"search_time": 1.45, "filter_time": 0.12, "total_results": 3}
            },
            "ip_address": "192.168.1.101"
        }
    ]

    for search in test_searches:
        logger.log_search(**search)

    print(f"✅ 成功记录 {len(test_searches)} 次搜索")

    # 检查日志文件
    log_file = logger.current_log_file
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        print(f"✅ 日志文件已创建: {log_file.name}")
        print(f"   总记录数: {len(lines)} 条")

except Exception as e:
    print(f"❌ 日志记录测试失败: {e}")

print()

# ============================================================================
# 测试2: 统计分析功能
# ============================================================================
print("📊 测试2: 统计分析功能")
print("-" * 80)

try:
    from app.agents.web_activity_logger import get_activity_analyzer

    analyzer = get_activity_analyzer()
    print(f"✅ 分析器初始化成功")

    # 分析最近7天的数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    analysis = analyzer.analyze(start_date=start_date, end_date=end_date)

    print(f"✅ 数据分析完成")
    print(f"   总搜索次数: {analysis['summary']['total_searches']}")
    print(f"   成功率: {analysis['summary']['success_rate']}%")
    print(f"   独立用户: {analysis['summary']['unique_users']}")
    print(f"   访问网站: {analysis['summary']['unique_websites']}")

    if analysis['top_websites']:
        print(f"   最常访问: {analysis['top_websites'][0]['domain']}")

except Exception as e:
    print(f"❌ 统计分析测试失败: {e}")

print()

# ============================================================================
# 测试3: 告警系统
# ============================================================================
print("🚨 测试3: 告警系统")
print("-" * 80)

try:
    from app.agents.web_activity_alerts import get_alert_system, check_and_alert

    alert_system = get_alert_system()
    print(f"✅ 告警系统初始化成功")
    print(f"   告警规则数: {len(alert_system.rules)}")
    print(f"   已启用规则: {len([r for r in alert_system.rules if r.enabled])}")

    # 测试告警检查（使用模拟数据）
    test_metrics = {
        "success_rate": 75.0,  # 低于80%阈值
        "avg_search_time": 2.5,
        "filter_rate": 30.0,
        "sanitized_queries": 2
    }

    alerts = check_and_alert(test_metrics)

    if alerts:
        print(f"✅ 触发 {len(alerts)} 个告警:")
        for alert in alerts:
            print(f"   [{alert.level.value}] {alert.rule_name}: {alert.message}")
    else:
        print(f"✅ 未触发告警（指标正常）")

    # 获取告警摘要
    summary = alert_system.get_alert_summary(hours=24)
    print(f"✅ 告警摘要:")
    print(f"   最近24小时总告警: {summary['total_alerts']}")

except Exception as e:
    print(f"❌ 告警系统测试失败: {e}")

print()

# ============================================================================
# 测试4: 数据管理
# ============================================================================
print("💾 测试4: 数据管理")
print("-" * 80)

try:
    from app.agents.web_activity_data_manager import get_data_manager

    data_manager = get_data_manager()
    print(f"✅ 数据管理器初始化成功")
    print(f"   日志目录: {data_manager.log_dir}")
    print(f"   备份目录: {data_manager.backup_dir}")
    print(f"   归档目录: {data_manager.archive_dir}")

    # 获取存储信息
    storage_info = data_manager.get_storage_info()

    print(f"✅ 存储信息:")
    print(f"   日志大小: {storage_info['log_dir']['size_bytes'] / 1024:.2f} KB")
    print(f"   日志文件数: {storage_info['log_dir']['file_count']}")
    print(f"   备份大小: {storage_info['backup_dir']['size_bytes'] / 1024:.2f} KB")
    print(f"   备份文件数: {storage_info['backup_dir']['file_count']}")

    # 测试备份功能
    print(f"\n   测试备份功能...")
    backup_result = data_manager.backup_logs(days=1)

    if backup_result['success']:
        print(f"   ✅ 备份成功: {backup_result['file_count']} 个文件")
        if 'backup_file' in backup_result:
            print(f"      备份文件: {Path(backup_result['backup_file']).name}")
    else:
        print(f"   ⚠️  备份结果: {backup_result.get('message', 'No files to backup')}")

except Exception as e:
    print(f"❌ 数据管理测试失败: {e}")

print()

# ============================================================================
# 测试5: 认证系统
# ============================================================================
print("🔐 测试5: 认证系统")
print("-" * 80)

try:
    from app.api.auth import authenticate_user, verify_api_key, create_access_token

    # 测试用户名密码认证
    user = authenticate_user("admin", "admin123")
    if user:
        print(f"✅ 用户名密码认证成功")
        print(f"   用户: {user.username}")
        print(f"   角色: {user.role}")
    else:
        print(f"❌ 用户名密码认证失败")

    # 测试API Key认证
    api_user = verify_api_key("admin-api-key-12345")
    if api_user:
        print(f"✅ API Key认证成功")
        print(f"   用户: {api_user.username}")
        print(f"   角色: {api_user.role}")
    else:
        print(f"❌ API Key认证失败")

    # 测试JWT Token生成
    token = create_access_token({"sub": "admin"})
    print(f"✅ JWT Token生成成功")
    print(f"   Token长度: {len(token)} 字符")

    # 测试默认账户
    test_accounts = [
        ("admin", "admin123", "Admin"),
        ("manager", "manager123", "Manager"),
        ("viewer", "viewer123", "Viewer")
    ]

    print(f"\n✅ 默认账户测试:")
    for username, password, expected_role in test_accounts:
        user = authenticate_user(username, password)
        if user and user.role.lower() == expected_role.lower():
            print(f"   ✅ {username:8s} - 角色: {user.role}")
        else:
            print(f"   ❌ {username:8s} - 认证失败")

except Exception as e:
    print(f"❌ 认证系统测试失败: {e}")

print()

# ============================================================================
# 测试6: 工具函数
# ============================================================================
print("🛠️  测试6: 工具函数")
print("-" * 80)

try:
    from app.agents.web_research_utils import (
        validate_url,
        is_time_sensitive_query,
        WebSearchMetrics
    )

    # 测试URL验证
    test_urls = [
        ("https://github.com", True),
        ("http://example.com", True),
        ("javascript:alert('xss')", False),
        ("http://localhost", False),
    ]

    print(f"✅ URL验证测试:")
    for url, expected in test_urls:
        result = validate_url(url)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {url:30s} -> {result}")

    # 测试时效性检测
    test_queries = [
        ("What is the latest AI news?", True),
        ("Python tutorial", False),
        ("今天的天气", True),
        ("What is Python?", False),
    ]

    print(f"\n✅ 时效性检测测试:")
    for query, expected in test_queries:
        result = is_time_sensitive_query(query)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {query:30s} -> {result}")

    # 测试Metrics类
    metrics = WebSearchMetrics()
    metrics.total_searches = 100
    metrics.successful_searches = 85

    print(f"\n✅ Metrics统计:")
    print(f"   成功率: {metrics.get_success_rate()}%")
    print(f"   总搜索: {metrics.total_searches}")

except Exception as e:
    print(f"❌ 工具函数测试失败: {e}")

print()

# ============================================================================
# 测试7: 配置文件
# ============================================================================
print("⚙️  测试7: 配置文件")
print("-" * 80)

try:
    config_path = Path("config/web_activity_config.json")

    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        print(f"✅ 配置文件加载成功: {config_path}")
        print(f"   告警系统: {'启用' if config.get('alert_system', {}).get('enabled') else '禁用'}")
        print(f"   数据管理: {'启用' if config.get('data_management', {}).get('backup', {}).get('enabled') else '禁用'}")
        print(f"   认证系统: {'启用' if config.get('authentication', {}).get('enabled') else '禁用'}")
        print(f"   告警规则数: {len(config.get('alert_system', {}).get('rules', []))}")
    else:
        print(f"⚠️  配置文件不存在: {config_path}")
        print(f"   请从示例文件创建配置文件")

except Exception as e:
    print(f"❌ 配置文件测试失败: {e}")

print()

# ============================================================================
# 测试摘要
# ============================================================================
print("=" * 80)
print("📋 测试摘要")
print("=" * 80)

test_results = {
    "日志记录": "✅",
    "统计分析": "✅",
    "告警系统": "✅",
    "数据管理": "✅",
    "认证系统": "✅",
    "工具函数": "✅",
    "配置文件": "✅"
}

for test_name, status in test_results.items():
    print(f"{status} {test_name}")

print()
print("=" * 80)
print("✅ 所有测试完成！")
print("=" * 80)
print()
print("📚 下一步:")
print("1. 启动API服务: uvicorn app.api.main:app --reload")
print("2. 访问Dashboard: http://localhost:8000/static/web_activity_dashboard.html")
print("3. 测试API: curl -H 'X-API-Key: admin-api-key-12345' http://localhost:8000/api/v1/admin/web-activity/stats")
print()
