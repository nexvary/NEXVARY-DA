import tempfile
import unittest
from pathlib import Path

from nexvary_da.errors import PermissionDenied
from nexvary_da.intelligence import (
    CloudIntelligenceGateway,
    ReasoningRequest,
    ReasoningResponse,
)
from nexvary_da.modes import ValidationPlanner, WorkMode
from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.state import ProjectState
from nexvary_da.terminal_pool import TerminalPool


class FakeProvider:
    name = "fake-cloud"

    def reason(self, request):
        return ReasoningResponse(
            provider=self.name,
            model="test-model",
            plan=f"plan:{request.goal}:{request.mode.value}",
        )


class HybridArchitectureTests(unittest.TestCase):
    def test_cloud_reasoning_requires_network_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = ProjectState(root)
            guard = WorkspaceGuard(
                [WorkspacePolicy.create(root, {Permission.READ}, "test")]
            )
            gateway = CloudIntelligenceGateway(guard, str(root), state, FakeProvider())
            with self.assertRaises(PermissionDenied):
                gateway.reason(ReasoningRequest("fix UI"))
            state.close()

    def test_cloud_reasoning_does_not_require_local_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = ProjectState(root)
            guard = WorkspaceGuard(
                [
                    WorkspacePolicy.create(
                        root, {Permission.READ, Permission.NETWORK}, "test"
                    )
                ]
            )
            response = CloudIntelligenceGateway(
                guard, str(root), state, FakeProvider()
            ).reason(ReasoningRequest("fix UI", mode=WorkMode.FAST))
            self.assertEqual("fake-cloud", response.provider)
            self.assertIn("fast", response.plan)
            state.close()

    def test_work_modes_have_distinct_validation_cost(self):
        fast = ValidationPlanner.plan(WorkMode.FAST, ["a.py"])
        engineer = ValidationPlanner.plan(WorkMode.ENGINEER, ["a.py"])
        release = ValidationPlanner.plan(WorkMode.RELEASE, ["a.py"])
        self.assertFalse(fast.run_related_tests)
        self.assertTrue(engineer.run_related_tests)
        self.assertFalse(engineer.run_full_release_gate)
        self.assertTrue(release.run_full_release_gate)
        self.assertTrue(release.clean_build)

    def test_terminal_pool_reuses_worker_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = WorkspaceGuard(
                [
                    WorkspacePolicy.create(
                        root, {Permission.READ, Permission.SHELL}, "test"
                    )
                ]
            )
            pool = TerminalPool(guard, root)
            try:
                builder = pool.get("builder-1")
                self.assertIs(builder, pool.get("builder-1"))
                self.assertIsNot(builder, pool.get("qa-1"))
                self.assertEqual(("builder-1", "qa-1"), pool.owners())
            finally:
                pool.close_all()


if __name__ == "__main__":
    unittest.main()
