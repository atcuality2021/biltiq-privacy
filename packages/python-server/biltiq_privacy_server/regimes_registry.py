# SPDX-License-Identifier: MIT
"""Regime registry — the single id → ``Regime`` seam (BILTIQ-013, AC3).

``_REGIMES`` is the one place a compliance regime is wired into the server. A
Phase C regime registers here; routers and handlers never name a concrete
regime class, so the resolution path stays uniform. ``resolve_regime`` is the
only lookup, so an unknown id always fails the same way — with
:class:`~biltiq_privacy_server.errors.UnknownRegimeError`, mapped to HTTP 422.
"""
from __future__ import annotations

from biltiq_privacy import DPDPRegime, Regime

from biltiq_privacy_server.errors import UnknownRegimeError

#: id → regime class. The single seam for Phase C regimes; the key is the
#: regime's public ``regime_id`` (``DPDPRegime.regime_id == "DPDP-2023"``).
_REGIMES: dict[str, type[Regime]] = {
    "DPDP-2023": DPDPRegime,
}


def resolve_regime(regime_id: str) -> Regime:
    """Instantiate the regime registered under ``regime_id``.

    Args:
        regime_id: the public regime identifier, e.g. ``"DPDP-2023"``.

    Returns:
        A fresh instance of the registered :class:`~biltiq_privacy.Regime`.

    Raises:
        UnknownRegimeError: if no regime is registered under ``regime_id``. The
            message lists the known ids (none of which is PII).
    """
    try:
        regime_cls = _REGIMES[regime_id]
    except KeyError as exc:
        known = ", ".join(sorted(_REGIMES))
        raise UnknownRegimeError(
            f"Unknown regime '{regime_id}'. Known regimes: {known}."
        ) from exc
    return regime_cls()
