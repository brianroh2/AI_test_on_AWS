"""
P5_04_tooluse_toolresult.py
────────────────────────────────────────────────────────────────────
Tool Use 챕터 04 — toolResult 반환 및 4단계 완전 구현

04-1. run_tool() — toolUse 블록 → toolResult 변환 함수
04-2. ask_with_tools() — 4단계 완전 구현
04-3. 테스트 실행

실행:
  python3 P5_04_tooluse_toolresult.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import json
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)

print("=" * 60)
print("  Part 5 — toolResult 반환 및 4단계 완전 구현")
print("=" * 60)

# ── get_weather 함수 ─────────────────────────────────────────────
def get_weather(city: str) -> dict:
    """wttr.in에서 날씨 조회 (format=3)."""
    url = f"https://wttr.in/{quote(city)}?format=3"
    try:
        req = Request(url, headers={"User-Agent": "curl/8"})
        with urlopen(req, timeout=10) as resp:
            report = resp.read().decode("utf-8").strip()
        return {"city": city, "report": report}
    except (URLError, HTTPError) as e:
        return {"city": city, "error": f"날씨 조회 실패: {e}"}

# ── toolSpec / toolConfig ────────────────────────────────────────
WEATHER_TOOL = {
    "toolSpec": {
        "name": "get_weather",
        "description": "도시의 현재 날씨를 조회합니다. 도시명은 영문으로 입력합니다.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "도시명. 예: Seoul, Tokyo, New York"}
                },
                "required": ["city"],
            }
        },
    }
}

TOOL_FUNCTIONS = {"get_weather": get_weather}
TOOL_CONFIG    = {"tools": [WEATHER_TOOL]}

# ── 04-1. run_tool() ─────────────────────────────────────────────
def run_tool(tool_use: dict) -> dict:
    """toolUse 블록을 받아 toolResult 형식으로 반환."""
    func   = TOOL_FUNCTIONS.get(tool_use["name"])
    result = func(**tool_use["input"]) if func else {"error": "알 수 없는 도구"}
    return {
        "toolResult": {
            "toolUseId": tool_use["toolUseId"],
            # dict → {"json": ...}, 문자열 → {"text": ...}
            "content": [{"json": result}],
        }
    }

print("\n[04-1] run_tool() 동작 확인")
sample_tool_use = {
    "name": "get_weather",
    "input": {"city": "Seoul"},
    "toolUseId": "test-id-001",
}
tool_result = run_tool(sample_tool_use)
print(f"  toolUseId : {tool_result['toolResult']['toolUseId']}")
print(f"  content   : {tool_result['toolResult']['content']}")

# ── 04-2. ask_with_tools() — 4단계 완전 구현 ────────────────────
def ask_with_tools(user_text: str) -> str:
    """4단계 Tool Use 완전 구현."""
    messages = [{"role": "user", "content": [{"text": user_text}]}]

    # [1] converse + toolConfig
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=messages,
        toolConfig=TOOL_CONFIG,
        inferenceConfig={"maxTokens": 500},
    )

    # 도구 호출 없으면 바로 반환
    if resp["stopReason"] != "tool_use":
        return resp["output"]["message"]["content"][0]["text"]

    assistant_msg = resp["output"]["message"]
    messages.append(assistant_msg)  # [2] assistant 메시지 히스토리 추가

    # [3] toolResult 수집
    tool_results = []
    for block in assistant_msg["content"]:
        if "toolUse" in block:
            print(f"  [ 도구 호출 ] {block['toolUse']['name']}({block['toolUse']['input']})")
            tool_results.append(run_tool(block["toolUse"]))

    messages.append({"role": "user", "content": tool_results})  # user 역할로 추가

    # [4] 최종 converse
    final = bedrock.converse(
        modelId=MODEL_ID,
        messages=messages,
        toolConfig=TOOL_CONFIG,
        inferenceConfig={"maxTokens": 500},
    )
    return final["output"]["message"]["content"][0]["text"]

# ── 04-3. 테스트 ─────────────────────────────────────────────────
print("\n[04-3] 테스트 실행")
tests = [
    "서울 날씨 지금 어때?",
    "도쿄 날씨는?",   # 도구 호출
]

for q in tests:
    print(f"\n  질문: {q}")
    answer = ask_with_tools(q)
    print(f"  답변: {answer[:150]}")

print(f"""
  ─────────────────────────────────────────────
  핵심 포인트:
    run_tool()  : toolUse 블록 → toolResult 변환
    content 형식: dict → {{"json": ...}}
    messages 순서: user → assistant → user(toolResult)
      (roles must alternate 규칙)
    toolUseId   : toolUse.toolUseId와 반드시 일치
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P5_04 완료 → P5_05 로 진행하세요")
print("=" * 60)
