"""
P6_09_strands_mcp.py
────────────────────────────────────────────────────────────────────
Strands 챕터 09 — MCP (Model Context Protocol)

09-1. FastMCP 서버 확인 (woodcutter_mcp_server.py)
09-2. StdioServerParameters + MCPClient 연결
09-3. list_tools_sync() — 도구 목록 확인
09-4. Agent에 MCP 도구 등록 + 대화

실행:
  python3 P6_09_strands_mcp.py
────────────────────────────────────────────────────────────────────
"""

import os
import sys
import boto3
from pathlib import Path
from mcp import StdioServerParameters
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

session = boto3.Session(region_name=REGION)

model = BedrockModel(
    model_id=MODEL_ID,
    boto_session=session,
    streaming=True,
)

# MCP 서버 파일 경로 (현재 스크립트와 같은 디렉토리)
SERVER_PATH = Path(__file__).parent / "woodcutter_mcp_server.py"

print("=" * 60)
print("  Part 6 — MCP (Model Context Protocol)")
print("=" * 60)

# ── 09-1. FastMCP 서버 파일 확인 ─────────────────────────────────
print("\n[09-1] FastMCP 서버 파일 확인")

if SERVER_PATH.exists():
    print(f"  ✅ {SERVER_PATH.name} 존재")
else:
    print(f"  ❌ {SERVER_PATH} 없음 — woodcutter_mcp_server.py 를 먼저 생성하세요")
    sys.exit(1)

# ── 09-2. StdioServerParameters + MCPClient 연결 ─────────────────
print("\n[09-2] StdioServerParameters + MCPClient 연결")

stdio_params = StdioServerParameters(
    command=sys.executable,         # python3
    args=[str(SERVER_PATH)],        # woodcutter_mcp_server.py
    env={**os.environ, "FASTMCP_LOG_LEVEL": "ERROR"},   # 배너 로그 억제
)

def make_transport():
    from mcp.client.stdio import stdio_client
    return stdio_client(stdio_params)

print(f"  command : {sys.executable}")
print(f"  args    : {SERVER_PATH.name}")

# ── 09-3. list_tools_sync() — 도구 목록 확인 ─────────────────────
print("\n[09-3] list_tools_sync() — MCP 도구 목록")

with MCPClient(make_transport) as mcp_client:
    tools = mcp_client.list_tools_sync()

    print(f"  등록된 도구 수: {len(tools)}개")
    for t in tools:
        print(f"  • {t.tool_name}")

    # ── 09-4. Agent에 MCP 도구 등록 + 대화 ───────────────────────
    print("\n[09-4] Agent에 MCP 도구 등록 + 대화")

    agent = Agent(
        model=model,
        tools=tools,
        system_prompt="당신은 나무꾼 조수입니다. 주어진 도구를 활용해 나무 작업을 도와줍니다.",
    )

    print("  질문 1: 참나무 5그루 벌목 → 목재 가공 → 판매")
    print("-" * 40)
    agent(
        "참나무(oak) 5그루를 베고, 나온 통나무를 전부 목재로 가공한 뒤, "
        "목재를 개당 150원에 팔아줘. 최종 수익은 얼마야?"
    )

print(f"""
  ─────────────────────────────────────────────
  MCP 핵심 구조:

  ① FastMCP 서버 (woodcutter_mcp_server.py)
      @mcp.tool() 로 도구 정의
      mcp.run(transport="stdio") 로 실행

  ② MCPClient (strands.tools.mcp)
      StdioServerParameters(command, args)
      with MCPClient(transport_callable) as client:
          tools = client.list_tools_sync()

  ③ Agent(tools=tools)
      MCP 도구를 일반 도구처럼 등록 및 사용

  ⚠️  주의:
    • MCPClient 는 with 블록 안에서만 유효
    • Agent 호출도 with 블록 안에서 수행해야 함
    • FastMCP 배너 로그 억제: FASTMCP_LOG_LEVEL=ERROR
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P6_09 완료 → P6_10 으로 진행하세요")
print("=" * 60)
