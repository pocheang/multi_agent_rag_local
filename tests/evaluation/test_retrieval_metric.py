"""A retrieval metric that runs on a fresh checkout, and can fail.

CLAUDE.md has claimed P@5 > 0.85 for a long time with nothing measuring it: the
one endpoint that could reads `data/evaluation/*.json`, `data/` is gitignored, so
on every checkout where nobody hand-placed a file it returned 404. This suite
ships a corpus and a query set instead, and measures them through the real
`KnowledgeOrchestrator`.

The most important test here is `test_a_mismatched_scope_returns_nothing`.
`mask_evidence` runs inside `_retrieve_source`, so a corpus whose ownership
metadata does not match the scope drops every item and scores 0.00 for a reason
that has nothing to do with retrieval quality -- indistinguishable from a broken
retriever. Proving the metric can fail is the precondition for trusting it when
it passes, the same lesson as the sensitive-content gate.

Scores are pinned exactly rather than ratcheted on an aggregate: BM25 over a
fixed JSONL file is deterministic, and with twelve queries an aggregate moves in
jumps of about 0.08, so a ratchet on it would either never fire or fire on a
corpus edit. Per-query reciprocal ranks name the offender instead.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.evaluation.retrieval_eval import (
    CORPUS_PATHS,
    QUERY_PATHS,
    eval_scope,
    load_corpus_sources,
    load_queries,
    measure,
    resolve,
)

TRACKED_CORPUS = Path("config/eval/retrieval_corpus.jsonl")
TRACKED_QUERIES = Path("config/eval/retrieval_queries.json")


@pytest.fixture
def eval_corpus(monkeypatch):
    """Point BM25 at the tracked corpus and clear its cache.

    `_load_bm25` is `lru_cache(maxsize=1)`, so without the reset this would
    silently measure whatever corpus the developer's own `data/chunks` holds --
    a green number about the wrong documents.
    """

    from app.retrievers.bm25_retriever import reset_bm25_cache

    monkeypatch.setenv("CORPUS_STORE_PATH", str(TRACKED_CORPUS))
    get_settings.cache_clear()
    reset_bm25_cache()
    try:
        yield
    finally:
        get_settings.cache_clear()
        reset_bm25_cache()


# --- the set ships and is internally consistent -----------------------------


def test_the_tracked_default_exists_and_is_the_fallback_path():
    assert TRACKED_CORPUS.exists()
    assert TRACKED_QUERIES.exists()
    assert CORPUS_PATHS[-1] == TRACKED_CORPUS
    assert QUERY_PATHS[-1] == TRACKED_QUERIES


def test_the_shipped_set_is_actually_tracked_by_git():
    """Existing on disk is not the same as shipping, and this file nearly proved it.

    `.gitignore` carries a blanket `*.jsonl` for logs, which silently swallowed
    `config/eval/retrieval_corpus.jsonl` -- so the corpus would have been absent
    on every fresh clone while every test here passed on the machine that wrote
    it. That is precisely the defect this whole suite exists to fix, one level up.

    `git check-ignore` rather than `git ls-files`, so this also fails for a file
    that was force-added once and would go invisible on its next edit.
    """

    for path in (TRACKED_CORPUS, TRACKED_QUERIES):
        result = subprocess.run(
            ["git", "check-ignore", str(path)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[2],
        )
        # Exit code 1 means "not ignored", which is what we need.
        assert result.returncode == 1, f"{path} is gitignored and would not survive a clone"


def test_a_deployment_override_wins_over_the_tracked_default():
    """Same precedence as `_BENCHMARK_QUERY_PATHS`: `data/` first."""

    assert CORPUS_PATHS[0].parts[0] == "data"
    assert QUERY_PATHS[0].parts[0] == "data"


def test_a_genuinely_missing_set_raises_rather_than_scoring_zero():
    with pytest.raises(FileNotFoundError):
        resolve((Path("nowhere/absent-corpus.jsonl"),))


def test_every_expected_doc_exists_in_the_shipped_corpus():
    """The single most valuable test here.

    An `expected_docs` entry naming a source the corpus does not contain scores
    0.0 forever and looks exactly like a retrieval failure. `expected_docs` holds
    *source identifiers*, not document ids -- the retriever reports
    `metadata["source"]`.
    """

    sources = set(load_corpus_sources(TRACKED_CORPUS))
    missing = {
        expected
        for query in load_queries(TRACKED_QUERIES)
        for expected in query.expected_docs
        if expected not in sources
    }

    assert missing == set()


def test_the_query_set_is_bilingual():
    """An English-only evaluation corpus measures the wrong system in an
    application whose reason for existing is that it works in Chinese."""

    queries = load_queries(TRACKED_QUERIES)
    chinese = [query for query in queries if any("一" <= ch <= "鿿" for ch in query.query)]

    assert len(chinese) >= 4
    assert len(queries) - len(chinese) >= 4


def test_the_corpus_declares_the_ownership_the_scope_asks_for():
    """The precondition for the metric meaning anything -- see the module
    docstring on `mask_evidence`."""

    from app.evaluation.retrieval_eval import EVAL_TENANT, EVAL_USER

    rows = [json.loads(line) for line in TRACKED_CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert rows
    for row in rows:
        metadata = row["metadata"]
        assert metadata["tenant_id"] == EVAL_TENANT
        assert metadata["owner_user_id"] == EVAL_USER


# --- the measurement --------------------------------------------------------


# Queries whose gold document BM25 alone cannot rank first, with the reason and
# the rank it does achieve. A ratchet, not an allowlist: the rank is pinned
# exactly, so an improvement fails this test just as a regression does, and the
# entry has to be revisited either way.
#
# These are not defects in the retriever. They are the boundary of lexical
# matching, which is why the production pipeline fuses BM25 with vector search --
# something this BM25-only harness deliberately does not do.
KNOWN_LEXICAL_LIMITS = {
    # "产假" is a substring of "陪产假", so both documents contain the query's
    # only content token. BM25 rewards matches and does not penalise a document
    # for carrying extra terms, so the shorter (陪产假) document wins on length
    # normalisation. The reverse direction -- asking about 陪产假 -- *is* fixed by
    # the CJK bigrams, because "陪产" then discriminates.
    "q-15": 2,
}


@pytest.mark.asyncio
async def test_every_query_puts_its_gold_document_first(eval_corpus: None):
    """A hand-authored micro-corpus should be unambiguous, so rank 1 everywhere.

    Deterministic input, deterministic retriever: this is pinned rather than
    ratcheted. The per-query map is asserted so a failure names the query.
    """

    queries = load_queries(TRACKED_QUERIES)
    score = await measure(queries, eval_scope(load_corpus_sources(TRACKED_CORPUS)))

    expected = {query.id: KNOWN_LEXICAL_LIMITS.get(query.id, 1) for query in queries}

    assert score.ranks == expected, f"MRR={score.mrr:.4f} P@5={score.precision_at_5:.4f} ranks={score.ranks}"


@pytest.mark.asyncio
async def test_a_word_jieba_does_not_know_is_still_retrievable(eval_corpus: None):
    """The assertion that would have caught the tokenizer.

    jieba splits "年假" into two single characters, and the tokenizer dropped
    every single-character token -- so the word vanished from the query and from
    the document alike and could never match. Not ranked badly: absent.
    """

    queries = [query for query in load_queries(TRACKED_QUERIES) if query.id == "q-13"]
    score = await measure(queries, eval_scope(load_corpus_sources(TRACKED_CORPUS)))

    assert score.ranks["q-13"] == 1


@pytest.mark.asyncio
async def test_a_mismatched_scope_returns_nothing(eval_corpus: None):
    """Prove the metric can fail before trusting it when it passes.

    A scope that authorizes no source drops every item in `mask_evidence`, and
    the score goes to zero without anything about retrieval having changed. If
    this test ever passes *and* the one above also passes with the same scope
    bug present, the metric is measuring nothing.
    """

    queries = load_queries(TRACKED_QUERIES)
    score = await measure(queries, eval_scope(("eval://corpus/not-a-real-document.md",)))

    assert score.mrr == 0.0
    assert score.precision_at_5 == 0.0
    assert set(score.ranks.values()) == {0}


@pytest.mark.asyncio
async def test_precision_at_five_is_capped_by_one_gold_document_per_query(eval_corpus: None):
    """Pins why P@5 here is 0.2 and why that is not a bad score.

    Each query names exactly one relevant document, so at most one of five
    retrieved items can be relevant. Reading this number against a P@5 > 0.85
    target quoted for a multi-gold corpus is a category error, and it is an easy
    one to make from a metrics table.
    """

    queries = load_queries(TRACKED_QUERIES)

    assert all(len(query.expected_docs) == 1 for query in queries)

    score = await measure(queries, eval_scope(load_corpus_sources(TRACKED_CORPUS)))

    assert score.precision_at_5 == pytest.approx(0.2)
