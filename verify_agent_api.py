"""
Verify the agent quality stats API returns correct data.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.agent_execution_tracker import get_tracker
from app.api.routes.admin_agent_quality import get_agent_quality_stats
import asyncio
import json

async def verify_api():
    """Verify the API returns correct data."""

    # Mock admin dependency
    class MockAdmin:
        pass

    print("=" * 60)
    print("Verifying Agent Quality Stats API")
    print("=" * 60)

    try:
        # Call the API endpoint
        result = await get_agent_quality_stats(_admin=MockAdmin())

        print("\nAPI Response Structure:")
        print(f"  - summary: {bool(result.get('summary'))}")
        print(f"  - agents: {len(result.get('agents', []))} agents")
        print(f"  - timeline: {len(result.get('timeline', []))} data points")
        print(f"  - error_distribution: {len(result.get('error_distribution', {}))} error types")

        print("\nSummary Metrics:")
        summary = result.get('summary', {})
        print(f"  - Total Agents: {summary.get('total_agents')}")
        print(f"  - Total Executions: {summary.get('total_executions')}")
        print(f"  - Overall Success Rate: {summary.get('overall_success_rate'):.2%}")
        print(f"  - Avg Response Time: {summary.get('avg_response_time'):.2f}s")
        print(f"  - Active Agents: {summary.get('active_agents')}")

        print("\nAgent Details:")
        for agent in result.get('agents', [])[:5]:  # Show top 5
            print(f"  - {agent['agent_name']}:")
            print(f"      Executions: {agent['total_executions']}")
            print(f"      Success Rate: {agent['success_rate']:.2%}")
            print(f"      Avg Time: {agent['avg_execution_time']:.2f}s")
            print(f"      Failures: {agent['failure_count']}")

        print("\nTimeline Sample (last 5 hours):")
        for entry in result.get('timeline', [])[-5:]:
            print(f"  - {entry['timestamp']}: {entry['success']} success, {entry['failure']} failures")

        print("\nError Distribution:")
        for error_type, count in result.get('error_distribution', {}).items():
            print(f"  - {error_type}: {count}")

        print("\n" + "=" * 60)
        print("VERIFICATION COMPLETE")
        print("=" * 60)

        # Check for issues
        issues = []

        if summary.get('total_executions', 0) == 0:
            issues.append("No executions found - run generate_test_agent_data.py first")

        if summary.get('avg_response_time', 0) > 10:
            issues.append("Average response time seems too high (>10s) - check unit conversion")

        if not result.get('timeline'):
            issues.append("Timeline data is empty")

        if issues:
            print("\nISSUES FOUND:")
            for issue in issues:
                print(f"  X {issue}")
        else:
            print("\n✓ All checks passed! API is working correctly.")

        return result

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(verify_api())
