from unittest.mock import MagicMock, Mock, patch

from app.agents.synthesizer.generation import _build_prompt_with_language, synthesize_answer


def test_build_prompt_with_language_chinese():
    """Test prompt builder includes Chinese language hint"""
    prompt = _build_prompt_with_language(
        question="什么是RAG？",
        detected_language="zh",
        skill_name="answer_with_citations",
        vector_context="RAG是检索增强生成...",
    )

    assert "[Language: zh]" in prompt
    assert "什么是RAG？" in prompt
    assert "RAG是检索增强生成..." in prompt


def test_build_prompt_with_language_english():
    """Test prompt builder includes English language hint"""
    prompt = _build_prompt_with_language(
        question="What is RAG?",
        detected_language="en",
        skill_name="answer_with_citations",
        vector_context="RAG is Retrieval-Augmented Generation...",
    )

    assert "[Language: en]" in prompt
    assert "What is RAG?" in prompt


@patch("app.agents.synthesizer.generation.detect_language")
@patch("app.agents.synthesizer.generation.get_chat_model")
@patch("app.agents.synthesizer.generation.bulkhead")
def test_synthesize_answer_detects_chinese(mock_bulkhead, mock_get_chat_model, mock_detect_language):
    """Test synthesize_answer detects Chinese and returns detected_language"""
    # Setup mocks
    mock_detect_language.return_value = "zh"
    mock_model = MagicMock()
    mock_model.invoke.return_value = Mock(content="RAG是检索增强生成技术")
    mock_get_chat_model.return_value = mock_model
    mock_bulkhead.return_value.__enter__ = Mock()
    mock_bulkhead.return_value.__exit__ = Mock()

    # Call synthesize_answer
    result = synthesize_answer(
        question="什么是RAG？", skill_name="answer_with_citations", vector_context="RAG是检索增强生成..."
    )

    # Verify language detection was called
    mock_detect_language.assert_called_once_with("什么是RAG？")

    # Verify result structure
    assert isinstance(result, dict)
    assert "answer" in result
    assert "detected_language" in result
    assert result["detected_language"] == "zh"
    assert isinstance(result["answer"], str)


@patch("app.agents.synthesizer.generation.detect_language")
@patch("app.agents.synthesizer.generation.get_chat_model")
@patch("app.agents.synthesizer.generation.bulkhead")
def test_synthesize_answer_detects_english(mock_bulkhead, mock_get_chat_model, mock_detect_language):
    """Test synthesize_answer detects English and returns detected_language"""
    # Setup mocks
    mock_detect_language.return_value = "en"
    mock_model = MagicMock()
    mock_model.invoke.return_value = Mock(content="RAG is Retrieval-Augmented Generation")
    mock_get_chat_model.return_value = mock_model
    mock_bulkhead.return_value.__enter__ = Mock()
    mock_bulkhead.return_value.__exit__ = Mock()

    # Call synthesize_answer
    result = synthesize_answer(
        question="What is RAG?",
        skill_name="answer_with_citations",
        vector_context="RAG is Retrieval-Augmented Generation...",
    )

    # Verify language detection was called
    mock_detect_language.assert_called_once_with("What is RAG?")

    # Verify result structure
    assert isinstance(result, dict)
    assert "answer" in result
    assert "detected_language" in result
    assert result["detected_language"] == "en"


@patch("app.agents.synthesizer.generation.detect_language")
@patch("app.agents.synthesizer.generation.get_chat_model")
@patch("app.agents.synthesizer.generation.bulkhead")
def test_synthesize_answer_force_language_override(mock_bulkhead, mock_get_chat_model, mock_detect_language):
    """Test force_language parameter overrides auto-detection"""
    # Setup mocks
    mock_model = MagicMock()
    mock_model.invoke.return_value = Mock(content="RAG is Retrieval-Augmented Generation")
    mock_get_chat_model.return_value = mock_model
    mock_bulkhead.return_value.__enter__ = Mock()
    mock_bulkhead.return_value.__exit__ = Mock()

    # Call with force_language='en' on Chinese question
    result = synthesize_answer(question="什么是RAG？", skill_name="answer_with_citations", force_language="en")

    # Verify detect_language was NOT called (force_language overrides)
    mock_detect_language.assert_not_called()

    # Verify forced language is used
    assert result["detected_language"] == "en"


@patch("app.agents.synthesizer.generation.detect_language")
@patch("app.agents.synthesizer.generation.get_chat_model")
@patch("app.agents.synthesizer.generation.bulkhead")
def test_synthesize_answer_returns_fallback_on_error(mock_bulkhead, mock_get_chat_model, mock_detect_language):
    """Test synthesize_answer returns fallback message on error"""
    # Setup mocks to raise exception
    mock_detect_language.return_value = "zh"
    mock_get_chat_model.side_effect = Exception("LLM service unavailable")

    # Call synthesize_answer
    result = synthesize_answer(question="什么是RAG？", skill_name="answer_with_citations")

    # Verify fallback message is returned
    assert isinstance(result, dict)
    assert "answer" in result
    assert "detected_language" in result
    assert result["detected_language"] == "zh"
    assert "抱歉" in result["answer"] or "暂时不可用" in result["answer"]
