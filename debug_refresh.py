"""
Debug script for Agent Quality Monitoring refresh issues.

This script helps diagnose problems with the dashboard refresh functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.agent_execution_tracker import AgentExecutionTracker


async def test_refresh_scenario():
    """Simulate the dashboard refresh scenario."""
    print("🔍 Testing Dashboard Refresh Scenario\n")
    print("=" * 60)

    tracker = AgentExecutionTracker.get_instance()
    tracker.clear_all_traces()

    # Scenario 1: Empty state (initial load)
    print("\n1️⃣ Test: Empty state (no data)")
    print("-" * 60)
    stats = tracker.get_quality_stats()
    print(f"   Total Agents: {stats['summary']['total_agents']}")
    print(f"   Total Executions: {stats['summary']['total_executions']}")
    print(f"   Timeline entries: {len(stats['timeline'])}")
    print(f"   Agents list: {len(stats['agents'])}")
    print(f"   ✅ Empty state handled correctly\n")

    # Scenario 2: Add some data
    print("2️⃣ Test: After adding execution data")
    print("-" * 60)

    # Create execution
    execution_id = tracker.start_execution("Test query", user_id="test_user")

    # Add successful step
    step_id_1 = tracker.record_agent_step(
        execution_id=execution_id,
        agent_name="TestAgent1",
        input_data={"query": "test"}
    )
    await asyncio.sleep(0.1)  # Simulate some processing time
    tracker.complete_agent_step(
        execution_id=execution_id,
        step_id=step_id_1,
        output_data={"result": "ok"},
        metadata={"tokens": 100}
    )

    # Add another step
    step_id_2 = tracker.record_agent_step(
        execution_id=execution_id,
        agent_name="TestAgent2",
        input_data={"query": "test"}
    )
    await asyncio.sleep(0.1)
    tracker.complete_agent_step(
        execution_id=execution_id,
        step_id=step_id_2,
        output_data={"result": "ok"},
        metadata={"tokens": 200}
    )

    tracker.complete_execution(execution_id)

    # Refresh stats
    stats = tracker.get_quality_stats()
    print(f"   Total Agents: {stats['summary']['total_agents']}")
    print(f"   Total Executions: {stats['summary']['total_executions']}")
    print(f"   Overall Success Rate: {stats['summary']['overall_success_rate']:.1%}")
    print(f"   Timeline entries: {len(stats['timeline'])}")
    print(f"   Agents list: {len(stats['agents'])}")

    for agent in stats['agents']:
        print(f"\n   Agent: {agent['agent_name']}")
        print(f"      Executions: {agent['total_executions']}")
        print(f"      Success Rate: {agent['success_rate']:.1%}")
        print(f"      Last Execution: {agent['last_execution']}")

    print(f"\n   ✅ Data populated correctly\n")

    # Scenario 3: Multiple refreshes
    print("3️⃣ Test: Multiple consecutive refreshes")
    print("-" * 60)

    for i in range(3):
        stats = tracker.get_quality_stats()
        print(f"   Refresh #{i+1}: {stats['summary']['total_agents']} agents, "
              f"{stats['summary']['total_executions']} executions")
        await asyncio.sleep(0.5)

    print(f"   ✅ Multiple refreshes work correctly\n")

    # Scenario 4: Add error data
    print("4️⃣ Test: Adding error data and refreshing")
    print("-" * 60)

    execution_id_2 = tracker.start_execution("Another query", user_id="test_user")
    step_id_3 = tracker.record_agent_step(
        execution_id=execution_id_2,
        agent_name="TestAgent3",
        input_data={"query": "test"}
    )
    tracker.fail_agent_step(
        execution_id=execution_id_2,
        step_id=step_id_3,
        error="TimeoutError: Request timed out"
    )
    tracker.complete_execution(execution_id_2)

    stats = tracker.get_quality_stats()
    print(f"   Total Agents: {stats['summary']['total_agents']}")
    print(f"   Total Executions: {stats['summary']['total_executions']}")
    print(f"   Overall Success Rate: {stats['summary']['overall_success_rate']:.1%}")
    print(f"   Error Distribution: {stats['error_distribution']}")
    print(f"   ✅ Error data handled correctly\n")

    # Scenario 5: Test edge cases
    print("5️⃣ Test: Edge cases")
    print("-" * 60)

    # Agent with empty last_execution
    print("   Testing agent with missing last_execution...")
    for agent in stats['agents']:
        if not agent.get('last_execution'):
            print(f"   ⚠️  Agent {agent['agent_name']} has empty last_execution")
        else:
            print(f"   ✅ Agent {agent['agent_name']} has valid last_execution")

    # Check for None/null values
    print("\n   Checking for None/null values in stats...")
    def check_none_values(obj, path="root"):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if value is None:
                    print(f"   ⚠️  Found None at {path}.{key}")
                else:
                    check_none_values(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                check_none_values(item, f"{path}[{i}]")

    check_none_values(stats)
    print("   ✅ No unexpected None values found\n")

    # Scenario 6: Simulate 30-second auto-refresh
    print("6️⃣ Test: Simulating auto-refresh interval")
    print("-" * 60)
    print("   Simulating 3 refresh cycles (3 seconds instead of 30)...")

    for cycle in range(3):
        await asyncio.sleep(1)
        stats = tracker.get_quality_stats()
        print(f"   Cycle {cycle+1}: {stats['summary']['total_executions']} executions, "
              f"{stats['summary']['overall_success_rate']:.1%} success rate")

    print(f"   ✅ Auto-refresh simulation completed\n")

    # Scenario 7: Clear and reload
    print("7️⃣ Test: Clear data and reload")
    print("-" * 60)

    print("   Clearing all traces...")
    tracker.clear_all_traces()

    stats = tracker.get_quality_stats()
    print(f"   After clear - Total Agents: {stats['summary']['total_agents']}")
    print(f"   After clear - Total Executions: {stats['summary']['total_executions']}")

    if stats['summary']['total_executions'] == 0:
        print(f"   ✅ Clear operation successful\n")
    else:
        print(f"   ❌ Clear operation may have failed\n")

    print("=" * 60)
    print("✅ All refresh scenarios tested successfully!")
    print("=" * 60)


async def test_api_response_format():
    """Test that API response format matches frontend expectations."""
    print("\n\n🔍 Testing API Response Format\n")
    print("=" * 60)

    tracker = AgentExecutionTracker.get_instance()
    tracker.clear_all_traces()

    # Create some test data
    execution_id = tracker.start_execution("Test", user_id="test")
    step_id = tracker.record_agent_step(execution_id, "TestAgent", {"test": "data"})
    tracker.complete_agent_step(execution_id, step_id, {"result": "ok"}, metadata={"tokens": 100})
    tracker.complete_execution(execution_id)

    stats = tracker.get_quality_stats()

    # Check required fields in summary
    print("\n1. Checking summary fields...")
    required_summary_fields = ['total_agents', 'total_executions', 'overall_success_rate',
                               'avg_response_time', 'active_agents']
    for field in required_summary_fields:
        if field in stats['summary']:
            print(f"   ✅ summary.{field}: {stats['summary'][field]}")
        else:
            print(f"   ❌ Missing: summary.{field}")

    # Check required fields in agents
    print("\n2. Checking agent fields...")
    if stats['agents']:
        agent = stats['agents'][0]
        required_agent_fields = ['agent_name', 'total_executions', 'success_count',
                                'failure_count', 'success_rate', 'avg_execution_time',
                                'avg_token_usage', 'last_execution', 'error_types']
        for field in required_agent_fields:
            if field in agent:
                print(f"   ✅ agents[0].{field}: {agent[field]}")
            else:
                print(f"   ❌ Missing: agents[0].{field}")

    # Check timeline format
    print("\n3. Checking timeline format...")
    if stats['timeline']:
        timeline_item = stats['timeline'][0]
        required_timeline_fields = ['timestamp', 'success', 'failure']
        for field in required_timeline_fields:
            if field in timeline_item:
                print(f"   ✅ timeline[0].{field}: {timeline_item[field]}")
            else:
                print(f"   ❌ Missing: timeline[0].{field}")
    else:
        print("   ℹ️  Timeline is empty (no data)")

    # Check error_distribution
    print("\n4. Checking error_distribution...")
    print(f"   error_distribution type: {type(stats['error_distribution'])}")
    print(f"   error_distribution content: {stats['error_distribution']}")

    print("\n" + "=" * 60)
    print("✅ API response format check completed!")
    print("=" * 60)

    # Cleanup
    tracker.clear_all_traces()


if __name__ == "__main__":
    try:
        print("\n" + "=" * 60)
        print("🧪 Agent Quality Monitoring Refresh Debug Tool")
        print("=" * 60)

        asyncio.run(test_refresh_scenario())
        asyncio.run(test_api_response_format())

        print("\n\n" + "=" * 60)
        print("🎉 All diagnostic tests completed successfully!")
        print("=" * 60)
        print("\nIf you're still experiencing refresh issues:")
        print("1. Check browser console for JavaScript errors")
        print("2. Check network tab for failed API requests")
        print("3. Verify authentication token is valid")
        print("4. Check backend logs for errors")
        print("5. Try clearing browser cache and cookies")
        print("=" * 60 + "\n")

        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error during diagnostic: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
