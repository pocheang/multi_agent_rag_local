"""Test script for chart extraction functionality."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.ingestion.utils.chart_extractor import detect_chart_in_image, extract_chart_data_with_vision, chart_data_to_markdown
from app.ingestion.loaders.pdf_chart_loader import extract_charts_from_pdf


def test_chart_detection():
    """Test chart detection on sample images."""
    print("\n" + "=" * 80)
    print("TEST 1: Chart Detection")
    print("=" * 80)

    # This is a placeholder - in real usage, you'd load actual chart images
    print("\nℹ️  Chart detection requires actual image files to test.")
    print("   Use test_chart_extraction() with a real PDF containing charts.")


def test_chart_extraction(pdf_path: str):
    """Test chart extraction on a real PDF."""
    print("\n" + "=" * 80)
    print("TEST 2: Chart Extraction from PDF")
    print("=" * 80)

    path = Path(pdf_path)
    if not path.exists():
        print(f"❌ File not found: {pdf_path}")
        return

    print(f"\n📄 Testing on: {path.name}")

    # Extract charts
    print("\n🔧 Extracting charts...")
    try:
        chart_docs = extract_charts_from_pdf(path, use_vision=True, vision_model="gpt-4-vision")

        if not chart_docs:
            print("ℹ️  No charts detected in this PDF")
            return

        print(f"✅ Found {len(chart_docs)} chart(s)")

        for i, doc in enumerate(chart_docs, 1):
            print(f"\n📊 Chart {i}:")
            print(f"   Page: {doc.metadata.get('page')}")
            print(f"   Type: {doc.metadata.get('chart_type')}")
            print(f"   Confidence: {doc.metadata.get('detection_confidence', 0):.2f}")
            print(f"\n   Content preview (first 300 chars):")
            print("   " + "-" * 76)
            print("   " + doc.page_content[:300].replace("\n", "\n   "))
            print("   " + "-" * 76)

    except Exception as e:
        print(f"❌ Chart extraction failed: {e}")
        import traceback
        traceback.print_exc()


def test_vision_models():
    """Test different vision models."""
    print("\n" + "=" * 80)
    print("TEST 3: Vision Model Comparison")
    print("=" * 80)

    print("\n📋 Available vision models:")
    print("   1. gpt-4-vision (OpenAI GPT-4V)")
    print("   2. claude-3 (Anthropic Claude 3)")

    print("\n⚙️  Configuration:")
    print("   Set in .runtime/development.env:")
    print("   PDF_ENABLE_CHART_EXTRACTION=true")
    print("   PDF_CHART_VISION_MODEL=gpt-4-vision")
    print("   OPENAI_API_KEY=your_key_here")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("CHART EXTRACTION TESTS")
    print("=" * 80)

    test_chart_detection()
    test_vision_models()

    # Test on real PDF if provided
    if len(sys.argv) > 1:
        test_chart_extraction(sys.argv[1])
    else:
        print("\n" + "=" * 80)
        print("\nℹ️  To test on a real PDF with charts, run:")
        print("  python scripts/dev/test_chart_extraction.py <path_to_pdf>")
        print("\n⚠️  Note: Chart extraction requires:")
        print("  1. OpenAI API key (for GPT-4V) or Anthropic API key (for Claude 3)")
        print("  2. PDF_ENABLE_CHART_EXTRACTION=true in .runtime/development.env")

    print("\n" + "=" * 80)
    print("✅ Tests complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
