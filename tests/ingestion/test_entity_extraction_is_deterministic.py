"""The same document ingested twice gets the same chunk metadata.

`extract_entities` built every list as `list(set(matches))`, and set iteration
order over strings depends on `PYTHONHASHSEED`, which Python randomises per
process. Three of the five lists are then truncated -- acronyms and numbers to
five, URLs to three -- so it was not only the order that moved: *which* entities
were stored on a chunk changed between ingests of an unchanged document.

It surfaced on 2026-09-06 while characterising `split_documents_enhanced` for a
refactor. Two runs of the unmodified splitter produced different output, which is
the sort of thing a refactor's own verification is supposed to catch and the sort
of thing nothing else would have.

The decisive test here is the one that spends two subprocesses. An in-process
assertion cannot vary the hash seed, and asserting an expected order proves
determinism only by construction -- under the old code a single run could match
the expectation by luck. Running the same input under two different seeds and
comparing is the property itself.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

from app.ingestion.chunking.metadata import _first_distinct, extract_entities

# Seven distinct acronyms and four URLs, so both truncations have to choose; and
# repeats of "API" and "1.2.3", so de-duplication is exercised rather than assumed.
# (Note "S3" is not an acronym to this rule -- the pattern is letters only.)
_TEXT = (
    "The API talks to the CDN over TLS, with SSL at the edge and SSH for admin. "
    "The API also writes to S3. "
    "Contact ops@example.com or security@example.com. "
    "Hosts 10.0.0.1 and 10.0.0.2 answer on 8080. Versions 1.2.3, 1.2.4 and 1.2.3 again. "
    "See https://example.com/a and https://example.com/b and https://example.com/c "
    "and https://example.com/d. HTTP and DNS are handled upstream."
)


def test_entities_are_the_first_distinct_matches_in_order():
    entities = extract_entities(_TEXT)

    # Seven acronyms appear; the first five in order of appearance are kept, the
    # repeated "API" is not counted twice, and HTTP/DNS fall off the end because
    # they appear last -- not because of where a hash put them.
    assert entities["acronyms"] == ["API", "CDN", "TLS", "SSL", "SSH"]
    assert entities["numbers"] == ["10.0.0.1", "10.0.0.2", "8080", "1.2.3", "1.2.4"]
    assert entities["emails"] == ["ops@example.com", "security@example.com"]
    assert entities["ip_addresses"] == ["10.0.0.1", "10.0.0.2"]
    assert entities["urls"] == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]


def test_first_distinct_dedupes_without_reordering():
    assert _first_distinct(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]
    assert _first_distinct(["b", "a", "b", "c", "a"], 2) == ["b", "a"]
    assert _first_distinct([]) == []
    # A limit larger than the input is not an error, and does not pad.
    assert _first_distinct(["only"], 5) == ["only"]


def _extract_under_seed(seed: str) -> dict:
    """Run extract_entities in a fresh interpreter with a chosen hash seed."""
    program = textwrap.dedent(
        """
        import json, sys
        from app.ingestion.chunking.metadata import extract_entities
        print(json.dumps(extract_entities(sys.argv[1])))
        """
    )
    env = {**os.environ, "PYTHONHASHSEED": seed}
    result = subprocess.run(
        [sys.executable, "-c", program, _TEXT],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return json.loads(result.stdout)


def test_two_processes_with_different_hash_seeds_agree():
    """The property itself: same input, same metadata, regardless of process.

    This is what fails against the previous implementation. `list(set(...))` over
    six acronyms orders them by hash, so seeds 0 and 1 disagree about which five
    survive the truncation -- and both are equally "correct" to any assertion that
    only ever looks at one process.
    """
    assert _extract_under_seed("0") == _extract_under_seed("1")
