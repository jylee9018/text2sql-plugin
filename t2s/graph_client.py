"""Load the active semantic definition from Graph MCP without a local file."""

from __future__ import annotations

import asyncio
import os

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


DEFAULT_URL = "https://text2sql-graph-mcp-production.up.railway.app/mcp"


class GraphClientError(RuntimeError):
    pass


async def _fetch(model: str | None) -> dict:
    token = os.getenv("TEXT2SQL_MCP_TOKEN")
    if not token:
        raise GraphClientError("TEXT2SQL_MCP_TOKEN 이 없다. Graph MCP 인증을 설정한다")
    url = os.getenv("TEXT2SQL_MCP_URL", DEFAULT_URL)
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"},
                                   timeout=httpx2.Timeout(30.0, read=300.0)) as http:
        async with streamable_http_client(url, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("graph_get_model_snapshot", {"model": model})
    if result.is_error or not result.structured_content:
        raise GraphClientError("Graph MCP에서 활성 모델을 읽지 못했다")
    snapshot = result.structured_content
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("definition"), dict):
        raise GraphClientError("Graph MCP 응답에 실행용 정의가 없다")
    return snapshot


def fetch_model(model: str | None = None) -> dict:
    try:
        return asyncio.run(_fetch(model))
    except GraphClientError:
        raise
    except Exception as error:
        raise GraphClientError(f"Graph MCP 연결 실패: {type(error).__name__}") from error
