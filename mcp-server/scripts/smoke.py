"""Smoke-test the MCP server over real stdio: `uv run --project mcp-server python mcp-server/scripts/smoke.py`.
Needs a running EvalOps stack and EVALOPS_API_KEY."""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = os.path.join(os.path.dirname(__file__), "..", "server.py")


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=dict(os.environ))
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        print("tools:", sorted(t.name for t in tools.tools))
        projects = await session.call_tool("list_projects", {})
        print("list_projects:", projects.content[0].text[:200])
        runs = await session.call_tool("list_runs", {"project_id": 1, "limit": 2})
        print("list_runs:", runs.content[0].text[:300])
        cmp = await session.call_tool("compare_runs", {"base_run_id": 1, "head_run_id": 2})
        print("compare_runs:", cmp.content[0].text[:300])
        denied = await session.call_tool("get_run_summary", {"run_id": 999999})
        print("error surfaced as tool error:", denied.is_error if hasattr(denied, "is_error") else denied.isError)
        res = await session.read_resource("evalops://runs/1")
        print("resource bytes:", len(res.contents[0].text))
        prompts = await session.list_prompts()
        print("prompts:", [p.name for p in prompts.prompts])


asyncio.run(main())
