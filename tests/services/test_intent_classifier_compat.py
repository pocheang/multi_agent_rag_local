from app.services.query.intent_classifier import classify_intent_with_llm as canonical_classifier


def test_legacy_intent_classifier_path_exports_canonical_function():
    from app.services.llm_intent_classifier import classify_intent_with_llm as legacy_classifier

    assert legacy_classifier is canonical_classifier
