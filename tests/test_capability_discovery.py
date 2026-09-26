from __future__ import annotations

import unittest

from nexvary_da.capability_discovery import Capability, CapabilityCatalog, Trust


class CapabilityDiscoveryTests(unittest.TestCase):
    def test_unverified_discovery_never_authorizes_execution(self):
        catalog = CapabilityCatalog([Capability("Remote Video API", "api", ("video",), paid=True)])
        match = catalog.discover("video")[0]
        self.assertFalse(match.executable)

    def test_approved_local_provider_is_preferred(self):
        catalog = CapabilityCatalog([
            Capability("Cloud Video", "api", ("video",), paid=True, trust=Trust.REVIEWED),
            Capability("Local Video", "mcp", ("video",), local=True, privacy="local", trust=Trust.APPROVED),
        ])
        matches = catalog.discover("video")
        self.assertEqual("Local Video", matches[0].capability.name)
        self.assertTrue(matches[0].executable)

    def test_paid_provider_is_penalized_by_default(self):
        free = Capability("Free Vision", "api", ("vision",), trust=Trust.REVIEWED)
        paid = Capability("Paid Vision", "api", ("vision",), paid=True, trust=Trust.REVIEWED)
        matches = CapabilityCatalog([paid, free]).discover("vision")
        self.assertEqual("Free Vision", matches[0].capability.name)


if __name__ == "__main__":
    unittest.main()
