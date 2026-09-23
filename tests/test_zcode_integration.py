import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexvary_da.cli import build_parser
from nexvary_da.orchestration import ExecutionPlan
from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.process import ProcessResult
from nexvary_da.state import ProjectState
from nexvary_da.zcode_adapter import ZCodeAdapter, extract_execution_plan


class FakeRunner:
    def __init__(self, output='{"summary":"ok","steps":[{"action":"read_text","arguments":{"path":"README.md"},"reason":"inspect"}]}'):
        self.output = output
        self.calls = []

    def run(self, args, *, cwd, timeout=300, env=None):
        self.calls.append(
            {
                "args": list(args),
                "cwd": str(cwd),
                "timeout": timeout,
                "env": dict(env or {}),
            }
        )
        return ProcessResult(list(args), 0, self.output, 0.01)


class ZCodeIntegrationTests(unittest.TestCase):
    def test_extracts_direct_and_wrapped_plan(self):
        plan_text = '{"summary":"s","steps":[{"action":"read_text","arguments":{},"reason":"r"}]}'
        direct = extract_execution_plan(plan_text)
        wrapped = extract_execution_plan(json.dumps({"result": plan_text}))
        self.assertIsInstance(direct, ExecutionPlan)
        self.assertEqual("read_text", direct.steps[0].action)
        self.assertEqual("read_text", wrapped.steps[0].action)

    def test_adapter_forces_plan_mode_and_isolated_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_zcode = root / "zcode"
            fake_zcode.write_text("placeholder", encoding="utf-8")
            guard = WorkspaceGuard(
                [
                    WorkspacePolicy.create(
                        root,
                        {Permission.READ, Permission.WRITE, Permission.SHELL, Permission.NETWORK},
                        "zcode-test",
                    )
                ]
            )
            state = ProjectState(root)
            runner = FakeRunner()
            with patch.dict(os.environ, {"NEXVARY_DA_ZCODE_BIN": str(fake_zcode)}, clear=False):
                result = ZCodeAdapter(guard, runner, state, root).plan("inspect project")
            self.assertTrue(result.success)
            args = runner.calls[0]["args"]
            self.assertEqual("plan", args[args.index("--mode") + 1])
            self.assertNotIn("yolo", args)
            self.assertEqual("json", args[args.index("--output-format") + 1])
            self.assertIn("--disallowed-tools", args)
            self.assertIn("Bash", args)
            self.assertIn("Write", args)
            self.assertEqual(
                str(root / ".nexvary-da" / "zcode-data"),
                runner.calls[0]["env"]["ZCODE_DATA_BASE_DIR"],
            )
            state.close()

    def test_adapter_requires_network_before_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_zcode = root / "zcode"
            fake_zcode.write_text("placeholder", encoding="utf-8")
            guard = WorkspaceGuard(
                [
                    WorkspacePolicy.create(
                        root,
                        {Permission.READ, Permission.WRITE, Permission.SHELL},
                        "zcode-test",
                    )
                ]
            )
            state = ProjectState(root)
            runner = FakeRunner()
            with patch.dict(os.environ, {"NEXVARY_DA_ZCODE_BIN": str(fake_zcode)}, clear=False):
                with self.assertRaises(Exception):
                    ZCodeAdapter(guard, runner, state, root).plan("inspect project")
            self.assertEqual([], runner.calls)
            state.close()

    def test_cli_exposes_three_engine_modes(self):
        parser = build_parser()
        args = parser.parse_args(
            ["plan", "review this project", "--path", ".", "--engine", "hybrid", "--mode", "engineer"]
        )
        self.assertEqual("plan", args.command)
        self.assertEqual("hybrid", args.engine)
        self.assertEqual("review this project", args.goal)


if __name__ == "__main__":
    unittest.main()
