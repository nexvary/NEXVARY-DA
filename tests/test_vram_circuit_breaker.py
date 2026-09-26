from __future__ import annotations

import unittest

from nexvary_da.vram_circuit_breaker import VRAMCircuitBreaker


class VRAMCircuitBreakerTests(unittest.TestCase):
    def test_oom_degrades_twice_then_switches_backend(self):
        breaker = VRAMCircuitBreaker()
        first = breaker.decide("CUDA out of memory", 0)
        second = breaker.decide("CUDA OOM", 1)
        third = breaker.decide("allocation failed", 2)
        self.assertTrue(first.retry)
        self.assertEqual(0.75, first.resolution_scale)
        self.assertTrue(second.retry)
        self.assertEqual(0.5, second.resolution_scale)
        self.assertFalse(third.retry)
        self.assertTrue(third.backend_failed)

    def test_non_oom_failure_switches_immediately(self):
        decision = VRAMCircuitBreaker().decide("model file missing", 0)
        self.assertFalse(decision.retry)
        self.assertTrue(decision.backend_failed)


if __name__ == "__main__":
    unittest.main()
