"""A collection the retriever reads must be written by a class something builds.

`chart` was a retrieval modality for as long as this file's subject existed. It
was selected on visual wording, it queried `chart_descriptions`, and it returned
nothing every time -- because the only thing that writes that collection is
`ChartAnalyzer.index_chart`, and nothing in `app/` ever constructed a
`ChartAnalyzer`. The retriever swallowed the missing collection quietly
("Chart collection not found, skipping"), so the modality cost a retrieval slot
and an INFO line and bought nothing.

Two weaker checks would both have passed. `chart_descriptions` *was* named in
`app/` -- by its producer. `ChartAnalyzer.index_chart` *did* write it correctly.
The broken link is one further out: the class had no caller, so the method had no
caller, so the collection had no writer.

So this walks the chain the defect actually broke:

    collection name in the retriever
      -> the `index_*` method that writes it
        -> the class that method belongs to
          -> a construction of that class somewhere in `app/`

`ChartAnalyzer` was deleted (2026-09-05) rather than connected. The capability
did not go with it: a chart is an image, and `_index_images` captions images
through `app/ingestion/extraction/vision.py`, which follows
`IMAGE_CAPTION_BACKEND` and `MODEL_BACKEND` -- where `ChartAnalyzer` built its own
`AsyncOpenAI` client against a `VISION_MODEL` setting the admin page cannot
reach, outside the egress redaction the model wrapper applies.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

RETRIEVER = Path("app/retrievers/multimodal_retriever.py")
PRODUCER_DIR = Path("app/services/multimodal")
APP = Path("app")


def _collections_read_by_the_retriever() -> set[str]:
    """Every Chroma collection this retriever names, however it names it."""

    source = RETRIEVER.read_text(encoding="utf-8")
    names = set(re.findall(r'get_collection\(name=["\']([a-z_]+)["\']', source))
    names |= set(re.findall(r'^\s*"[a-z]+":\s*"([a-z_]+)",\s*$', source, re.MULTILINE))
    return names


def _writer_classes() -> dict[str, str]:
    """collection name -> the class whose `index_*` method writes it."""

    found: dict[str, str] = {}
    for path in PRODUCER_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for klass in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            for method in (m for m in klass.body if isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef)):
                if not method.name.startswith("index_"):
                    continue
                for node in ast.walk(method):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.endswith("s"):
                        found.setdefault(node.value, klass.name)
    return found


def _constructed_in_app(class_name: str) -> bool:
    """A call `ClassName(...)` anywhere in `app/` outside the class's own module."""

    pattern = re.compile(rf"\b{class_name}\(")
    for path in APP.rglob("*.py"):
        if path.parent == PRODUCER_DIR:
            continue
        if pattern.search(path.read_text(encoding="utf-8")):
            return True
    return False


def test_the_retriever_still_names_some_collections():
    """Otherwise every assertion below holds vacuously."""

    assert _collections_read_by_the_retriever()


def test_every_collection_the_retriever_reads_has_a_writer_something_constructs():
    """The assertion that would have caught it.

    On the code before this commit `chart_descriptions` resolved to
    `ChartAnalyzer`, which nothing constructs, and this fails.
    """

    writers = _writer_classes()

    for collection in sorted(_collections_read_by_the_retriever()):
        klass = writers.get(collection)
        assert klass, f"{collection} is queried but nothing in {PRODUCER_DIR} writes it"
        assert _constructed_in_app(klass), f"{collection} is written by {klass}, which nothing in app/ constructs"


def test_chart_is_gone_from_every_place_it_was_declared():
    """A half-removed modality is the failure mode here: the `Literal`, the
    default modality list, the fusion weight map and the collection map all had
    to agree, and nothing checked that they did."""

    assert "chart" not in RETRIEVER.read_text(encoding="utf-8").replace("# ", "\n# ").split("\n# ")[0]
    tree = ast.parse(RETRIEVER.read_text(encoding="utf-8"))
    literals = [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value == "chart"
    ]
    assert not literals, "a `chart` string literal survives in the retriever"
