"""Test script to check agent execution tracker status."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.agent_execution_tracker import get_tracker

def main():
    tracker = get_tracker()
    print(f"Total traces in memory: {len(tracker._traces)}")

    stats = tracker.get_execution_stats()
    print(f"\nAgent stats: {stats}")

    if not stats:
        print("\n❌ No agent execution data found!")
        print("This means no queries have been executed yet.")
        print("\nTo fix this:")
        print("1. Start the backend server: uvicorn app.api.main:app --reload --port 8000")
        print("2. Execute a query through the frontend or API")
        print("3. Refresh the Agent Health dashboard")
    else:
        print(f"\n✓ Found data for {len(stats)} agents")
        for agent_name, agent_stats in stats.items():
            print(f"  - {agent_name}: {agent_stats.get('executions', 0)} executions")

if __name__ == "__main__":
    main()
