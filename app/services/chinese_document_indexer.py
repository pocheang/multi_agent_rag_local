"""Compatibility re-export for :mod:`app.services.language.chinese_document_indexer`."""

from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("app.services.language.chinese_document_indexer")
