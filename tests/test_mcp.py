import tempfile
import unittest
from pathlib import Path

from mcp import Client

from nexvary_da.mcp_server import build_mcp_server
from nexvary_da.permissions import Permission
from nexvary_da.project import init_project


class MCPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_project_bound_tools_list_and_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(
                root,
                name="mcp-test",
                permissions={Permission.READ, Permission.WRITE, Permission.SHELL},
            )
            (root / "hello.txt").write_text("alpha\n", encoding="utf-8")
            mcp, service = build_mcp_server(root)
            try:
                async with Client(mcp, raise_exceptions=True) as client:
                    listed = await client.list_tools()
                    names = {tool.name for tool in listed.tools}
                    self.assertIn("project_status", names)
                    self.assertIn("read_text", names)
                    self.assertIn("terminal_exec", names)

                    read = await client.call_tool("read_text", {"path": "hello.txt"})
                    self.assertFalse(read.is_error)
                    self.assertEqual({"result": "alpha\n"}, read.structured_content)

                    write = await client.call_tool(
                        "write_text", {"path": "nested/out.txt", "content": "ok"}
                    )
                    self.assertFalse(write.is_error)
                    self.assertEqual("ok", (root / "nested" / "out.txt").read_text())

                    first = await client.call_tool("terminal_exec", {"command": "cd nested"})
                    self.assertFalse(first.is_error)
                    second = await client.call_tool(
                        "terminal_exec",
                        {"command": "python -c \"import os; print(os.path.basename(os.getcwd()))\""},
                    )
                    self.assertFalse(second.is_error)
                    self.assertEqual("nested", second.structured_content["output"])
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
