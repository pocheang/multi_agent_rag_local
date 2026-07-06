"""Test script to populate agent execution tracker with sample data."""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.agent_execution_tracker import get_tracker

def populate_sample_data():
    """Populate tracker with sample execution data."""
    tracker = get_tracker()

    print("Populating agent execution tracker with sample data...")

    # Simulate 10 successful queries
    for i in range(10):
        execution_id = tracker.start_execution(
            query=f"Test query {i+1}",
            user_id="test_user"
        )

        # Router agent
        router_step = tracker.record_agent_step(
            execution_id=execution_id,
            agent_name="router",
            input_data={"query": f"Test query {i+1}"}
        )
        time.sleep(0.01)
        tracker.complete_agent_step(
            execution_id=execution_id,
            step_id=router_step,
            output_data={"route": "vector", "confidence": 0.95}
        )

        # Vector retrieval agent
        retrieval_step = tracker.record_agent_step(
            execution_id=execution_id,
            agent_name="vector_retrieval",
            input_data={"query": f"Test query {i+1}", "route": "vector"}
        )
        time.sleep(0.05)
        tracker.complete_agent_step(
            execution_id=execution_id,
            step_id=retrieval_step,
            output_data={"chunks_count": 5},
            metadata={"tokens": 150}
        )

        # Synthesis agent
        synthesis_step = tracker.record_agent_step(
            execution_id=execution_id,
            agent_name="synthesis",
            input_data={"chunks_count": 5}
        )
        time.sleep(0.08)
        tracker.complete_agent_step(
            execution_id=execution_id,
            step_id=synthesis_step,
            output_data={"answer_length": 200},
            metadata={"tokens": 300}
        )

        # Complete execution
        tracker.complete_execution(execution_id, final_result={"success": True})

        print(f"[OK] Created execution {i+1}/10")

    # Simulate 2 failed queries
    for i in range(2):
        execution_id = tracker.start_execution(
            query=f"Failed query {i+1}",
            user_id="test_user"
        )

        router_step = tracker.record_agent_step(
            execution_id=execution_id,
            agent_name="router",
            input_data={"query": f"Failed query {i+1}"}
        )
        time.sleep(0.01)
        tracker.fail_agent_step(
            execution_id=execution_id,
            step_id=router_step,
            error="Timeout error"
        )

        tracker.fail_execution(execution_id, "Routing failed: Timeout")
        print(f"[FAIL] Created failed execution {i+1}/2")

    print("\n[OK] Sample data populated successfully!")

    # Display stats
    stats = tracker.get_execution_stats()
    print(f"\nCurrent stats:")
    for agent_name, agent_stats in stats.items():
        print(f"  {agent_name}: {agent_stats['executions']} executions, {agent_stats['failures']} failures")

if __name__ == "__main__":
    populate_sample_data()
