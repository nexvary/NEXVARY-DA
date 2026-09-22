import tempfile
import unittest
from pathlib import Path

from nexvary_da.goals import GoalEngine, RequirementStatus
from nexvary_da.state import ProjectState


class GoalEngineTests(unittest.TestCase):
    def test_required_obligations_need_explicit_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ProjectState(Path(tmp))
            engine = GoalEngine(state)
            goal = engine.create(
                "Release",
                ["compile", "tests", ("ui", False)],
                goal_id="release-1",
            )
            self.assertFalse(goal.complete)
            goal = engine.record("release-1", "compile", RequirementStatus.PASS, "compile output")
            self.assertFalse(goal.complete)
            goal = engine.record("release-1", "tests", RequirementStatus.FAIL, "1 failure")
            self.assertFalse(goal.complete)
            goal = engine.record("release-1", "tests", RequirementStatus.PASS, "all tests pass")
            self.assertTrue(goal.complete)
            state.close()

    def test_goal_survives_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = ProjectState(root)
            GoalEngine(first).create("Build", ["compile"], goal_id="g1")
            first.close()
            second = ProjectState(root)
            loaded = GoalEngine(second).load("g1")
            self.assertEqual("Build", loaded.title)
            self.assertEqual(RequirementStatus.PENDING, loaded.requirements[0].status)
            second.close()


if __name__ == "__main__":
    unittest.main()
