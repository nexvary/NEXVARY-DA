from __future__ import annotations

import unittest

from nexvary_da.adaptive_video import AdaptiveVideoRouter
from nexvary_da.compute_budget import ComputeBudgetDirector
from nexvary_da.hardware_profile import HardwareProfile


def hw(vram: float, cuda: bool = True) -> HardwareProfile:
    if not cuda or vram < 4:
        tier = "DIRECT"
    elif vram < 6:
        tier = "ECO"
    elif vram < 12:
        tier = "HYBRID"
    elif vram < 24:
        tier = "LOCAL_AI"
    else:
        tier = "MAX"
    return HardwareProfile("cpu", 16.0, "gpu", vram, cuda, True, tier)


class AdaptiveVideoTests(unittest.TestCase):
    def test_cpu_only_never_requests_generative_backend(self):
        plan = AdaptiveVideoRouter().plan(60, hw(0, False))
        self.assertEqual("DIRECT", plan.budget.tier)
        self.assertEqual(("direct",), plan.budget.backend_order)
        self.assertEqual(0, plan.budget.ai_seconds)

    def test_six_gb_uses_hybrid_with_direct_terminal_fallback(self):
        plan = AdaptiveVideoRouter().plan(60, hw(6))
        self.assertEqual("HYBRID", plan.budget.tier)
        self.assertLessEqual(plan.budget.ai_seconds, 10)
        self.assertEqual("direct", plan.budget.backend_order[-1])

    def test_router_skips_failed_backends(self):
        plan = AdaptiveVideoRouter().plan(60, hw(8))
        self.assertEqual("ltx-2b", AdaptiveVideoRouter.next_backend(plan, ("wangp",)))
        self.assertEqual("direct", AdaptiveVideoRouter.next_backend(
            plan, ("wangp", "ltx-2b", "cogvideox-2b")
        ))

    def test_compute_budget_is_bounded_for_long_ads(self):
        profile = hw(8)
        budget = ComputeBudgetDirector.plan(profile, 120)
        self.assertLessEqual(budget.ai_seconds, 10)
        self.assertLessEqual(budget.max_ai_clip_seconds, 4)


if __name__ == "__main__":
    unittest.main()
