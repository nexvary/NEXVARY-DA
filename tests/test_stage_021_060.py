import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexvary_da.errors import ConfigurationError
from nexvary_da.kernel import ToolContext, ToolKernel
from nexvary_da.orchestration import PlanExecutor, parse_plan_json
from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.provider_config import CloudProviderConfig
from nexvary_da.state import ProjectState
from nexvary_da.task_graph import TaskGraph, TaskStatus
from nexvary_da.test_selection import select_tests


class Stage021060Tests(unittest.TestCase):
    def test_provider_configuration_is_https_and_secret_is_env_only(self):
        with self.assertRaises(ConfigurationError):
            CloudProviderConfig("x", "http://example.test", "m", "KEY")
        config = CloudProviderConfig("x", "https://example.test/v1/chat", "m", "KEY")
        with patch.dict(os.environ, {"KEY": "secret"}, clear=False):
            self.assertEqual("secret", config.resolved_api_key())
            self.assertNotIn("secret", json.dumps(config.safe_summary()))

    def test_machine_plan_executes_only_registered_allowed_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ}, "t")])
            state = ProjectState(root)
            kernel = ToolKernel(guard, state)
            kernel.register("echo", lambda value: value)
            plan = parse_plan_json('{"steps":[{"action":"echo","arguments":{"value":"ok"}}]}')
            result = PlanExecutor(kernel, ToolContext(str(root), "coordinator"), allowed_actions={"echo"}).execute(plan)
            self.assertTrue(result[0].success)
            self.assertEqual("ok", result[0].output)
            state.close()

    def test_free_form_plan_is_not_executable(self):
        with self.assertRaises(ValueError):
            parse_plan_json("please edit files and push them")

    def test_task_graph_orders_and_blocks_dependents(self):
        graph = TaskGraph()
        graph.add("analyze", "Analyze")
        graph.add("build", "Build", dependencies={"analyze"})
        graph.add("test", "Test", dependencies={"build"})
        self.assertEqual(("analyze", "build", "test"), graph.topological_order())
        graph.set_status("analyze", TaskStatus.PASS)
        self.assertEqual("build", graph.ready()[0].task_id)
        graph.set_status("build", TaskStatus.FAIL)
        self.assertEqual(TaskStatus.BLOCKED, graph.node("test").status)

    def test_python_test_selector_prefers_direct_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n")
            (root / "src" / "demo.py").write_text("VALUE=1\n")
            (root / "tests" / "test_demo.py").write_text("pass\n")
            selection = select_tests(root, ["src/demo.py"])
            self.assertFalse(selection.full_suite)
            self.assertEqual(("tests/test_demo.py",), selection.candidates)


if __name__ == "__main__":
    unittest.main()
