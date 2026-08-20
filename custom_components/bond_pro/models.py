"""The Bond Pro integration models."""

from __future__ import annotations

from dataclasses import dataclass

from .bond_async_pro import BPUPSubscriptions

from .coordinator import BondFallbackCoordinator, BondTelemetryCoordinator
from .utils import BondHub


@dataclass
class BondData:
    """Runtime data for the Bond Pro integration."""

    hub: BondHub
    bpup_subs: BPUPSubscriptions
    fallback: BondFallbackCoordinator
    telemetry: BondTelemetryCoordinator
