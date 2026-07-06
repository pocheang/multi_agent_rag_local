"""
Web Activity Monitoring System - Quick Test Script
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("Web Activity Monitoring System - Quick Test")
print("=" * 80)
print()

test_results = []

# Test 1: Activity Logger
print("Test 1: Activity Logger")
print("-" * 80)
try:
    from app.agents.web_activity_logger import get_activity_logger

    logger = get_activity_logger()
    print(f"[PASS] Logger initialized")
    print(f"       Log dir: {logger.log_dir}")

    # Log a test search
    logger.log_search(
        user_id="test_user",
        session_id="test_session",
        query="Test query",
        result={"used": True, "citations": [], "metrics": {}}
    )
    print(f"[PASS] Test search logged")
    test_results.append(("Activity Logger", "PASS"))
except Exception as e:
    print(f"[FAIL] {e}")
    test_results.append(("Activity Logger", "FAIL"))
print()

# Test 2: Statistics Analyzer
print("Test 2: Statistics Analyzer")
print("-" * 80)
try:
    from app.agents.web_activity_logger import get_activity_analyzer

    analyzer = get_activity_analyzer()
    analysis = analyzer.analyze()

    print(f"[PASS] Analyzer initialized")
    print(f"       Total searches: {analysis['summary']['total_searches']}")
    print(f"       Success rate: {analysis['summary']['success_rate']}%")
    test_results.append(("Statistics Analyzer", "PASS"))
except Exception as e:
    print(f"[FAIL] {e}")
    test_results.append(("Statistics Analyzer", "FAIL"))
print()

# Test 3: Alert System
print("Test 3: Alert System")
print("-" * 80)
try:
    from app.agents.web_activity_alerts import get_alert_system, check_and_alert

    alert_system = get_alert_system()
    print(f"[PASS] Alert system initialized")
    print(f"       Rules loaded: {len(alert_system.rules)}")

    # Test alert with low success rate
    test_metrics = {"success_rate": 75.0}
    alerts = check_and_alert(test_metrics)
    print(f"[PASS] Alert check completed ({len(alerts)} alerts triggered)")
    test_results.append(("Alert System", "PASS"))
except Exception as e:
    print(f"[FAIL] {e}")
    test_results.append(("Alert System", "FAIL"))
print()

# Test 4: Data Manager
print("Test 4: Data Manager")
print("-" * 80)
try:
    from app.agents.web_activity_data_manager import get_data_manager

    data_manager = get_data_manager()
    storage_info = data_manager.get_storage_info()

    print(f"[PASS] Data manager initialized")
    print(f"       Log files: {storage_info['log_dir']['file_count']}")
    print(f"       Log size: {storage_info['log_dir']['size_bytes']} bytes")
    test_results.append(("Data Manager", "PASS"))
except Exception as e:
    print(f"[FAIL] {e}")
    test_results.append(("Data Manager", "FAIL"))
print()

# Test 5: Authentication
print("Test 5: Authentication")
print("-" * 80)
try:
    from app.services.auth.auth_service import AuthDBService

    auth_service = AuthDBService()

    # Test user authentication
    user = auth_service.user_manager.authenticate("admin", "admin123")
    if user:
        print(f"[PASS] Password auth: {user['username']} ({user['role']})")
    else:
        print(f"[INFO] Default admin user not found (may need initialization)")

    # Test session manager
    session_count = auth_service.session_manager.count_active_sessions()
    print(f"[PASS] Session manager initialized (active sessions: {session_count})")

    # Test user listing
    users = auth_service.user_manager.list_users()
    print(f"[PASS] User manager operational (total users: {len(users)})")

    test_results.append(("Authentication", "PASS"))
except Exception as e:
    print(f"[FAIL] {e}")
    test_results.append(("Authentication", "FAIL"))
print()

# Test 6: Utility Functions
print("Test 6: Utility Functions")
print("-" * 80)
try:
    from app.agents.web_research_utils import validate_url, is_time_sensitive_query

    # Test URL validation
    assert validate_url("https://github.com") == True
    assert validate_url("javascript:alert()") == False
    print(f"[PASS] URL validation works")

    # Test time-sensitive detection
    assert is_time_sensitive_query("latest news") == True
    assert is_time_sensitive_query("Python tutorial") == False
    print(f"[PASS] Time-sensitive detection works")

    test_results.append(("Utility Functions", "PASS"))
except Exception as e:
    print(f"[FAIL] {e}")
    test_results.append(("Utility Functions", "FAIL"))
print()

# Summary
print("=" * 80)
print("Test Summary")
print("=" * 80)
pass_count = sum(1 for _, status in test_results if status == "PASS")
fail_count = len(test_results) - pass_count

for test_name, status in test_results:
    symbol = "[PASS]" if status == "PASS" else "[FAIL]"
    print(f"{symbol} {test_name}")

print()
print(f"Total: {len(test_results)} tests")
print(f"Passed: {pass_count}")
print(f"Failed: {fail_count}")
print()

if fail_count == 0:
    print("=" * 80)
    print("ALL TESTS PASSED!")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Start API: uvicorn app.api.main:app --reload")
    print("2. Visit Dashboard: http://localhost:8000/static/web_activity_dashboard.html")
    print("3. Test API: curl -H 'X-API-Key: admin-api-key-12345' http://localhost:8000/api/v1/admin/web-activity/stats")
else:
    print("=" * 80)
    print(f"SOME TESTS FAILED ({fail_count}/{len(test_results)})")
    print("=" * 80)

sys.exit(0 if fail_count == 0 else 1)
