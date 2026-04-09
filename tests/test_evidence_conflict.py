from app.services.evidence_conflict import detect_evidence_conflict


def test_detect_evidence_conflict():
    citations = [
        {"content": "The service is vulnerable to SQL injection."},
        {"content": "The service is not vulnerable to SQL injection."},
    ]
    report = detect_evidence_conflict(citations)
    assert report["conflict"] is True
    assert report["pairs_checked"] == 1
