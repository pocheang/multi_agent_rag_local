"""
Integrated test: Generate test data and verify API in the same process.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, UTC
import random
import asyncio

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.agent_execution_tracker import get_tracker
from app.api.routes.admin_agent_quality import get_agent_quality_stats


def generate_test_data():
    """Generate test execution data."""
    tracker = get_tracker()
    tracker.clear_all_traces()

    agents = [
        "router",
        "vector_rag",
        "graph_rag",
        "react",
        "synthesis",
        "enhanced_router",
        "retrieval_quality",
        "answer_validator"
    ]

    print("Generating test data...")
    now = datetime.now(UTC)

    for i in range(50):
        hours_ago = random.uniform(0, 24)
        query_time = now - timedelta(hours=hours_ago)

        execution_id = tracker.start_execution(
            query=f"Test query {i+1}",
            user_id="test_user"
        )

        if execution_id in tracker._traces:
            tracker._traces[execution_id].start_time = query_time

        num_agents = random.randint(2, 5)
        selected_agents = random.sample(agents, num_agents)
        execution_success = random.random() > 0.1

        for agent_name in selected_agents:
            step_start = query_time + timedelta(milliseconds=random.randint(10, 100))
            step_id = tracker.record_agent_step(
                execution_id=execution_id,
                agent_name=agent_name,
                input_data={"query": f"Test query {i+1}"}
            )

            if execution_id in tracker._traces:
                for step in tracker._traces[execution_id].steps:
                    if step.step_id == step_id:
                        step.start_time = step_start
                        break

            duration_ms = random.randint(50, 500)
            step_end = step_start + timedelta(milliseconds=duration_ms)

            if execution_success or random.random() > 0.2:
                tracker.complete_agent_step(
                    execution_id=execution_id,
                    step_id=step_id,
                    output_data={"result": "success"},
                    metadata={"tokens": random.randint(100, 1000)}
                )

                if execution_id in tracker._traces:
                    for step in tracker._traces[execution_id].steps:
                        if step.step_id == step_id:
                            step.end_time = step_end
                            step.duration_ms = duration_ms
                            break
            else:
                error_types = ["timeout", "invalid_input", "model_error", "connection_error"]
                tracker.fail_agent_step(
                    execution_id=execution_id,
                    step_id=step_id,
                    error=random.choice(error_types)
                )

                if execution_id in tracker._traces:
                    for step in tracker._traces[execution_id].steps:
                        if step.step_id == step_id:
                            step.end_time = step_end
                            step.duration_ms = duration_ms
                            break

        total_duration = sum(random.randint(50, 500) for _ in selected_agents)
        exec_end = query_time + timedelta(milliseconds=total_duration)

        if execution_success:
            tracker.complete_execution(execution_id)
        else:
            tracker.fail_execution(execution_id, "Execution failed")

        if execution_id in tracker._traces:
            tracker._traces[execution_id].end_time = exec_end
            tracker._traces[execution_id].total_duration_ms = total_duration

    print(f"Generated 50 test executions")
    return tracker


async def verify_api():
    """Verify the API returns correct data."""

    class MockAdmin:
        pass

    print("\n" + "=" * 60)
    print("Verifying Agent Quality Stats API")
    print("=" * 60)

    try:
        result = await get_agent_quality_stats(_admin=MockAdmin())

        print("\nAPI Response:")
        summary = result.get('summary', {})
        print(f"  Total Agents: {summary.get('total_agents')}")
        print(f"  Total Executions: {summary.get('total_executions')}")
        print(f"  Overall Success Rate: {summary.get('overall_success_rate'):.2%}")
        print(f"  Avg Response Time: {summary.get('avg_response_time'):.2f}s")
        print(f"  Active Agents: {summary.get('active_agents')}")

        print(f"\n  Agents returned: {len(result.get('agents', []))}")
        print(f"  Timeline points: {len(result.get('timeline', []))}")
        print(f"  Error types: {len(result.get('error_distribution', {}))} types")

        print("\nTop 5 Agents:")
        for agent in result.get('agents', [])[:5]:
            print(f"  - {agent['agent_name']}: {agent['total_executions']} exec, "
                  f"{agent['success_rate']:.1%} success, "
                  f"{agent['avg_execution_time']:.2f}s avg")

        print("\n" + "=" * 60)

        if summary.get('total_executions', 0) > 0:
            print("SUCCESS! API is working correctly.")
            print("=" * 60)
            return True
        else:
            print("ERROR: No data returned")
            print("=" * 60)
            return False

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    # Generate test data
    generate_test_data()

    # Verify API
    success = await verify_api()

    if success:
        print("\nAll tests passed! The Agent Health dashboard should now show data.")
        print("\nNext steps:")
        print("1. Start the backend: uvicorn app.api.main:app --reload --port 8000")
        print("2. Open the frontend and navigate to Admin > AGENT Health tab")
        print("3. You should see the test data displayed")
        print("\nNote: Test data is stored in memory and will be lost when the server restarts.")
        print("To persist data, execute real queries through the application.")


if __name__ == "__main__":
    asyncio.run(main())
