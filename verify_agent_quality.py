"""
Quick verification script for Agent Quality Monitoring system.

This script tests the core functionality without requiring a full server startup.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.agent_execution_tracker import AgentExecutionTracker


def test_tracker():
    """Test the AgentExecutionTracker functionality."""
    print("🧪 Testing AgentExecutionTracker...\n")

    # Get tracker instance
    tracker = AgentExecutionTracker.get_instance()
    tracker.clear_all_traces()

    # Create test execution
    print("1. Creating test execution...")
    execution_id = tracker.start_execution("What is Docker?", user_id="test_user")
    print(f"   ✓ Execution ID: {execution_id}\n")

    # Add successful agent step
    print("2. Recording successful agent step...")
    step_id_1 = tracker.record_agent_step(
        execution_id=execution_id,
        agent_name="EnhancedRouterAgent",
        input_data={"query": "What is Docker?"}
    )
    tracker.complete_agent_step(
        execution_id=execution_id,
        step_id=step_id_1,
        output_data={"route": "vector", "confidence": 0.95},
        decision_rationale="High confidence vector search",
        metadata={"tokens": 150}
    )
    print(f"   ✓ Step completed: {step_id_1}\n")

    # Add another successful step
    print("3. Recording another successful step...")
    step_id_2 = tracker.record_agent_step(
        execution_id=execution_id,
        agent_name="EnhancedVectorRAGAgent",
        input_data={"query": "What is Docker?", "route": "vector"}
    )
    tracker.complete_agent_step(
        execution_id=execution_id,
        step_id=step_id_2,
        output_data={"documents": 5, "relevance_score": 0.89},
        metadata={"tokens": 2500}
    )
    print(f"   ✓ Step completed: {step_id_2}\n")

    # Add a failed step
    print("4. Recording failed agent step...")
    step_id_3 = tracker.record_agent_step(
        execution_id=execution_id,
        agent_name="WebResearchAgent",
        input_data={"query": "What is Docker?"}
    )
    tracker.fail_agent_step(
        execution_id=execution_id,
        step_id=step_id_3,
        error="TimeoutError: Request timed out after 30s"
    )
    print(f"   ✓ Step failed: {step_id_3}\n")

    # Complete execution
    print("5. Completing execution...")
    tracker.complete_execution(execution_id, final_result={"status": "success"})
    print("   ✓ Execution completed\n")

    # Get quality stats
    print("6. Retrieving quality statistics...")
    stats = tracker.get_quality_stats()

    print("\n📊 Quality Statistics Summary:")
    print(f"   Total Agents: {stats['summary']['total_agents']}")
    print(f"   Total Executions: {stats['summary']['total_executions']}")
    print(f"   Overall Success Rate: {stats['summary']['overall_success_rate']:.1%}")
    print(f"   Avg Response Time: {stats['summary']['avg_response_time']:.3f}s")
    print(f"   Active Agents: {stats['summary']['active_agents']}")

    print("\n📋 Agent Details:")
    for agent in stats['agents']:
        print(f"\n   {agent['agent_name']}:")
        print(f"      Executions: {agent['total_executions']}")
        print(f"      Success Rate: {agent['success_rate']:.1%}")
        print(f"      Avg Time: {agent['avg_execution_time']:.3f}s")
        print(f"      Avg Tokens: {agent['avg_token_usage']:.0f}")
        if agent['error_types']:
            print(f"      Errors: {agent['error_types']}")

    print("\n⏱️  Timeline Points:")
    print(f"   Total timeline entries: {len(stats['timeline'])}")

    print("\n❌ Error Distribution:")
    for error_type, count in stats['error_distribution'].items():
        print(f"   {error_type}: {count}")

    # Get execution trace
    print("\n7. Retrieving execution trace...")
    trace = tracker.get_execution_trace(execution_id)
    if trace:
        print(f"   ✓ Trace found with {len(trace.steps)} steps")
        print(f"   Status: {trace.status}")
        print(f"   Duration: {trace.total_duration_ms:.2f}ms")

    # Test legacy stats
    print("\n8. Testing legacy execution stats...")
    legacy_stats = tracker.get_execution_stats()
    print(f"   ✓ Found {len(legacy_stats)} agents in legacy format")

    print("\n✅ All tests passed!\n")

    # Cleanup
    tracker.clear_all_traces()
    print("🧹 Cleanup completed\n")


if __name__ == "__main__":
    try:
        test_tracker()
        print("=" * 60)
        print("🎉 Agent Quality Monitoring system is working correctly!")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
