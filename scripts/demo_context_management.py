"""
Demo script for context management service.

Demonstrates:
- Entity extraction and tracking
- Coreference resolution
- Topic tracking
- Multi-turn conversation handling
"""

from app.services.context_management import ContextManagementService


def print_section(title: str) -> None:
    """Print section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(turn: int, result) -> None:
    """Print processing result."""
    print(f"\n--- Turn {turn} ---")
    print(f"Original: {result.original}")
    print(f"Resolved: {result.resolved}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Entities: {result.entities_resolved}")
    print(f"Topic Switch: {result.topic_switch}")
    print(f"Needs Clarification: {result.needs_clarification}")


def demo_simple_coreference():
    """Demo simple coreference resolution."""
    print_section("Demo 1: Simple Coreference Resolution")

    service = ContextManagementService()
    session_id = "demo1"

    # Turn 1: Introduce entity
    result1 = service.process_query("苹果公司2023年的营收是多少？", session_id)
    print_result(1, result1)

    # Turn 2: Use pronoun
    result2 = service.process_query("它的市场份额呢？", session_id)
    print_result(2, result2)

    # Turn 3: Another pronoun
    result3 = service.process_query("它的CEO是谁？", session_id)
    print_result(3, result3)


def demo_multiple_entities():
    """Demo handling multiple entities."""
    print_section("Demo 2: Multiple Entity Tracking")

    service = ContextManagementService()
    session_id = "demo2"

    # Turn 1: Two entities
    result1 = service.process_query("特斯拉和比亚迪的销量对比", session_id)
    print_result(1, result1)

    # Turn 2: Reference to recent entity
    result2 = service.process_query("它的技术优势在哪里？", session_id)
    print_result(2, result2)

    # Turn 3: Reference to first entity
    result3 = service.process_query("第一家公司的市值", session_id)
    print_result(3, result3)


def demo_topic_switch():
    """Demo topic switch detection."""
    print_section("Demo 3: Topic Switch Detection")

    service = ContextManagementService()
    session_id = "demo3"

    # Turn 1: Financial topic
    result1 = service.process_query("苹果公司的营收和利润情况", session_id)
    print_result(1, result1)

    # Turn 2: Same topic
    result2 = service.process_query("它的财务报表怎么样？", session_id)
    print_result(2, result2)

    # Turn 3: Switch to product topic
    result3 = service.process_query("它的新产品有什么创新？", session_id)
    print_result(3, result3)


def demo_english():
    """Demo English language support."""
    print_section("Demo 4: English Language Support")

    service = ContextManagementService()
    session_id = "demo4"

    # Turn 1: Introduce entity
    result1 = service.process_query("What is Apple's revenue in 2023?", session_id)
    print_result(1, result1)

    # Turn 2: Use pronoun
    result2 = service.process_query("What is its market share?", session_id)
    print_result(2, result2)

    # Turn 3: Another query
    result3 = service.process_query("Who is the CEO?", session_id)
    print_result(3, result3)


def demo_entity_decay():
    """Demo entity decay over turns."""
    print_section("Demo 5: Entity Decay Weighting")

    service = ContextManagementService()
    session_id = "demo5"

    # Introduce multiple entities over turns
    queries = [
        "微软的云服务业务",
        "谷歌的搜索引擎市场",
        "亚马逊的电商平台",
        "脸书的社交网络",
        "特斯拉的电动车销量",
    ]

    for i, query in enumerate(queries, 1):
        result = service.process_query(query, session_id)
        print_result(i, result)

    # Check which entity is most relevant
    context = service.get_context(session_id)
    if context:
        print(f"\nCurrent Turn: {context.turn_count}")
        print(f"Current Topic: {context.current_topic}")
        print(f"Total Entities Seen: {len(context.entities)}")


def demo_clarification_needed():
    """Demo when clarification is needed."""
    print_section("Demo 6: Clarification Needed")

    service = ContextManagementService()
    session_id = "demo6"

    # Turn 1: No context yet, but use pronoun
    result1 = service.process_query("它的市场份额是多少？", session_id)
    print_result(1, result1)

    print("\nNote: Needs clarification because no entity in context yet!")


def demo_session_isolation():
    """Demo session isolation."""
    print_section("Demo 7: Session Isolation")

    service = ContextManagementService()

    # Session 1
    result1 = service.process_query("苹果公司的营收", session_id="session1")
    print(f"\nSession 1, Turn 1: {result1.original}")

    # Session 2 - should not know about Apple
    result2 = service.process_query("它的市场份额", session_id="session2")
    print(f"\nSession 2, Turn 1: {result2.original}")
    print(f"Resolved: {result2.resolved}")
    print(f"Needs Clarification: {result2.needs_clarification}")


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("  Context Management Service - Demo Scenarios")
    print("=" * 60)

    try:
        demo_simple_coreference()
        demo_multiple_entities()
        demo_topic_switch()
        demo_english()
        demo_entity_decay()
        demo_clarification_needed()
        demo_session_isolation()

        print("\n" + "=" * 60)
        print("  All demos completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
