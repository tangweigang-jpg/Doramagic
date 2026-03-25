"""Doramagic Controller — Outer layer of the dual-layer fusion architecture.

Flow control, lease management, degradation strategy, and platform adaptation.
"""

from doramagic_controller.flow_controller import FlowController
from doramagic_controller.lease_manager import LeaseManager
from doramagic_controller.budget_manager import BudgetManager
from doramagic_controller.state_definitions import Phase, TRANSITIONS

__all__ = ["FlowController", "LeaseManager", "BudgetManager", "Phase", "TRANSITIONS"]
