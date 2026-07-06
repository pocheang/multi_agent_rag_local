"""
Quick verification script to confirm all Agent Health Dashboard fixes.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, UTC
import random
import asyncio

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.agent_execution_tracker import get_tracker
from app.api.routes.admin_agent_quality import get_agent_quality_stats


def generate_minimal_test_data():
    """Generate minimal test data for verification."""
    tracker = get_tracker()
    tracker.clear_all_traces()

    now = datetime.now(UTC)

    # Create 1 simple execution with 2 agents
    execution_id = tracker.start_execution(query="Test query", user_id="test")

    # Override start time
    if execution_id in tracker._traces:
        tracker._traces[execution_id].start_time = now - timedelta(hours=1)

    # Agent 1: router (100ms)
    step1_id = tracker.record_agent_step(execution_id=execution_id, agent_name="router")
    if execution_id in tracker._traces:
        for step in tracker._traces[execution_id].steps:
            if step.step_id == step1_id:
                step.start_time = now - timedelta(hours=1)
                break

    tracker.complete_agent_step(
        execution_id=execution_id,
        step_id=step1_id,
        output_data={"result": "success"},
        metadata={"tokens": 150}
    )

    if execution_id in tracker._traces:
        for step in tracker._traces[execution_id].steps:
            if step.step_id == step1_id:
                step.end_time = step.start_time + timedelta(milliseconds=100)
                step.duration_ms = 100
                break

    # Agent 2: vector_rag (250ms)
    step2_id = tracker.record_agent_step(execution_id=execution_id, agent_name="vector_rag")
    if execution_id in tracker._traces:
        for step in tracker._traces[execution_id].steps:
            if step.step_id == step2_id:
                step.start_time = now - timedelta(hours=1) + timedelta(milliseconds=100)
                break

    tracker.complete_agent_step(
        execution_id=execution_id,
        step_id=step2_id,
        output_data={"result": "success"},
        metadata={"tokens": 500}
    )

    if execution_id in tracker._traces:
        for step in tracker._traces[execution_id].steps:
            if step.step_id == step2_id:
                step.end_time = step.start_time + timedelta(milliseconds=250)
                step.duration_ms = 250
                break

    # Complete execution
    tracker.complete_execution(execution_id)

    if execution_id in tracker._traces:
        tracker._traces[execution_id].end_time = now - timedelta(hours=1) + timedelta(milliseconds=350)
        tracker._traces[execution_id].total_duration_ms = 350


async def verify_fixes():
    """Verify all bug fixes."""

    class MockAdmin:
        pass

    print("=" * 70)
    print("AGENT HEALTH DASHBOARD - BUG FIX VERIFICATION")
    print("=" * 70)

    # Generate test data
    print("\n[1/4] Generating test data...")
    generate_minimal_test_data()
    print("      [OK] Test data generated")

    # Call API
    print("\n[2/4] Calling API endpoint...")
    try:
        result = await get_agent_quality_stats(_admin=MockAdmin())
        print("      [OK] API call successful")
    except Exception as e:
        print(f"      [FAIL] API call failed: {e}")
        return False

    # Verify response structure
    print("\n[3/4] Verifying response structure...")
    issues = []

    if not result.get('summary'):
        issues.append("Missing 'summary' field")
    if not isinstance(result.get('agents'), list):
        issues.append("'agents' is not a list")
    if not isinstance(result.get('timeline'), list):
        issues.append("'timeline' is not a list")
    if not isinstance(result.get('error_distribution'), dict):
        issues.append("'error_distribution' is not a dict")

    if issues:
        print("      [FAIL] Response structure issues:")
        for issue in issues:
            print(f"        - {issue}")
        return False

    print("      [OK] Response structure correct")

    # Verify bug fixes
    print("\n[4/4] Verifying bug fixes...")

    summary = result.get('summary', {})
    agents = result.get('agents', [])

    all_passed = True

    # Fix 1: Check response time unit (should be in seconds, not ms)
    avg_response_time = summary.get('avg_response_time', 0)
    if 0 < avg_response_time < 10:  # Should be < 1s for our test data (350ms)
        print("      [OK] Fix 1: Response time unit conversion (ms -> s) WORKING")
        print(f"        - Avg response time: {avg_response_time:.3f}s (expected ~0.35s)")
    else:
        print(f"      [FAIL] Fix 1: Response time unit FAILED")
        print(f"        - Got: {avg_response_time}s (expected ~0.35s)")
        all_passed = False

    # Fix 2: Check individual agent execution time unit
    if agents:
        agent = agents[0]
        agent_exec_time = agent.get('avg_execution_time', 0)
        if 0 < agent_exec_time < 1:  # Should be < 1s
            print("      [OK] Fix 2: Agent execution time unit conversion WORKING")
            print(f"        - {agent['agent_name']}: {agent_exec_time:.3f}s")
        else:
            print(f"      [FAIL] Fix 2: Agent execution time unit FAILED")
            print(f"        - Got: {agent_exec_time}s (too large)")
            all_passed = False

    # Fix 3: Check timeline data generation
    timeline = result.get('timeline', [])
    if timeline and len(timeline) > 0:
        print("      [OK] Fix 3: Timeline data generation WORKING")
        print(f"        - Timeline points: {len(timeline)}")
        # Check timeline has valid structure
        sample = timeline[0]
        if 'timestamp' in sample and 'success' in sample and 'failure' in sample:
            print("        - Timeline structure correct")
        else:
            print("        [FAIL] Timeline structure incorrect")
            all_passed = False
    else:
        print("      [FAIL] Fix 3: Timeline generation FAILED (empty)")
        all_passed = False

    # Summary
    print("\n" + "=" * 70)
    if all_passed:
        print("[SUCCESS] ALL BUG FIXES VERIFIED - DASHBOARD IS READY")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Start backend: uvicorn app.api.main:app --reload --port 8000")
        print("2. Generate test data via API or script")
        print("3. Open Admin Dashboard -> AGENT Health tab")
        print("4. Verify data displays correctly")
    else:
        print("[FAILED] SOME FIXES FAILED - REVIEW REQUIRED")
        print("=" * 70)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(verify_fixes())
    sys.exit(0 if success else 1)
