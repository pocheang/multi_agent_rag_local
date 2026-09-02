"""A forwarding wrapper must accept what its callers pass and forward it on.

`dispatch.py` calls `pdf_loader.load_pdf_enhanced` with `enable_cleaning`,
`enable_table_merging` and `enable_nested_table_handling`. The wrapper declared
only `(path, by_page)` and forwarded only those, so:

- `PDF_LOADER_MODE=docling_enhanced` and `docling_advanced` raised
  `TypeError: load_pdf_enhanced() got an unexpected keyword argument
  'enable_cleaning'` on the first PDF they touched, and
- `PDF_ENABLE_CLEANING` / `PDF_ENABLE_TABLE_MERGING` were settings that nothing
  downstream could act on -- configuration with no reader, reached through a
  different door than the ones the configuration pass closed.

The implementation underneath has supported all three from the start, and
`pdf_loader_advanced` calls it that way directly. Only the middle layer dropped
them, which is why nothing failed until someone selected one of those modes.

These tests check the *signature relationship* rather than "it does not raise".
A call-and-assert test would need a real PDF and a working docling install to
reach the same conclusion, and would go quiet the moment those were unavailable.
"""

from __future__ import annotations

import inspect

from app.ingestion.loaders import dispatch
from app.ingestion.loaders.pdf_loader import load_pdf_enhanced as wrapper
from app.ingestion.loaders.pdf_loader_enhanced import load_pdf_enhanced as implementation

PROCESSING_SWITCHES = ("enable_cleaning", "enable_table_merging", "enable_nested_table_handling")


def test_the_wrapper_accepts_every_switch_the_implementation_has() -> None:
    """Anything the real loader can be told, the wrapper must be able to relay."""

    wrapper_params = set(inspect.signature(wrapper).parameters)
    implementation_params = set(inspect.signature(implementation).parameters)

    missing = sorted(implementation_params - wrapper_params)
    assert not missing, (
        f"the wrapper cannot forward {missing}; a caller passing one gets TypeError, "
        "and any setting behind it silently does nothing"
    )


def test_the_switches_are_named_not_positional() -> None:
    """Callers pass them by keyword; positions would not match."""

    parameters = inspect.signature(wrapper).parameters

    for name in PROCESSING_SWITCHES:
        assert name in parameters, name
        assert parameters[name].default is True, f"{name} should default to on, as the implementation does"


def test_every_keyword_dispatch_passes_is_accepted() -> None:
    """Read the call sites rather than trusting that they were updated.

    This is the check that would have caught the original defect: `dispatch.py`
    names three keywords, and the wrapper accepted none of them.
    """

    source = inspect.getsource(dispatch)
    parameters = set(inspect.signature(wrapper).parameters)

    used = {name for name in PROCESSING_SWITCHES if f"{name}=" in source}
    assert used, "dispatch no longer passes any processing switch; this test has lost its subject"

    unsupported = sorted(used - parameters)
    assert not unsupported, f"dispatch.py passes {unsupported}, which the wrapper does not accept"
