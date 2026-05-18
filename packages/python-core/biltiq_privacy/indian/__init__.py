# SPDX-License-Identifier: MIT
"""Indian PII recogniser pack — regex patterns + Presidio adapter.

Sub-package layout (canonical, supersedes the legacy ``recognisers/india.py``
reference in ``docs/architecture/overview.md``):

* :mod:`biltiq_privacy.indian.patterns` — pure-``re`` regex pack + ``redact()``.
* :mod:`biltiq_privacy.indian.recognisers` — Presidio adapter + ``build_engine()``.

Public entry points are exposed by the sub-modules (``biltiq_privacy.indian.patterns.redact``,
``biltiq_privacy.indian.recognisers.build_engine``). This ``__init__`` is
intentionally thin — no top-level re-exports — to keep the import surface
explicit and to preserve the lazy-import contract (AC5): importing this
package alone must not transitively load ``presidio_analyzer`` or ``spacy``.
"""
from __future__ import annotations
