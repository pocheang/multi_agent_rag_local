"""jieba's dictionary was the tokenizer's only vocabulary.

Single-character tokens were dropped -- they carry almost no signal alone -- so a
word jieba does not know produced *nothing*, and two failures followed.

A word split entirely into single characters vanished from the query and the
document alike and could never match. Measured over 30 realistic domain terms
only one behaved that way, but it is a silent total failure and the affected set
is unpredictable.

The worse one is more common: jieba emits a sub-word, and the sub-word is used as
if it were the word. `陪产假` (paternity leave) tokenized to exactly `产假`
(maternity leave) -- an identical token set, so BM25 could not tell them apart
and a query about one ranked the other first. A wrong answer, not a missing one.

Character bigrams fix both without a dictionary.
"""

from __future__ import annotations

from app.retrievers.bm25_retriever import tokenize_chinese_aware as tokenize


def test_a_word_jieba_splits_into_single_characters_survives():
    """The assertion that would have caught it: this returned []."""

    assert "年假" in tokenize("年假有多少天")
    assert "年假" in tokenize("员工每年享有十五天带薪年假。")


def test_a_longer_term_is_distinguishable_from_the_shorter_one_inside_it():
    """`陪产假` and `产假` used to produce identical token sets."""

    longer = set(tokenize("陪产假"))
    shorter = set(tokenize("产假"))

    assert longer != shorter
    assert longer - shorter, "the longer term must contribute a token the shorter one does not"


def test_known_words_keep_their_whole_word_token():
    """Bigrams are added alongside jieba's tokens, not instead of them, so an
    exact word match keeps its weight."""

    tokens = tokenize("机器学习算法")

    assert "机器" in tokens
    assert "学习" in tokens


def test_english_is_untouched():
    assert tokenize("machine learning") == ["machine", "learning"]


def test_bigrams_do_not_cross_punctuation():
    """A run ends at punctuation; a bigram spanning two clauses would be noise
    that matches nothing meaningful."""

    tokens = tokenize("考勤记录，迟到提醒")

    assert "录迟" not in tokens
