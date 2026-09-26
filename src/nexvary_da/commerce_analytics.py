from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True,slots=True)
class FunnelMetrics:
    leads:int; qualified:int; orders:int; paid:int; revenue:float
    lead_to_order:float; order_to_paid:float


def funnel_metrics(*,leads:int,qualified:int,orders:int,paid:int,revenue:float)->FunnelMetrics:
    return FunnelMetrics(leads,qualified,orders,paid,float(revenue),
                         (orders/leads if leads else 0.0),(paid/orders if orders else 0.0))
