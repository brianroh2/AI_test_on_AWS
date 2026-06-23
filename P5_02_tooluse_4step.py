"""
P5_02_tooluse_4step.py
────────────────────────────────────────────────────────────────────
Tool Use 챕터 02 — 4단계 흐름 이해

4단계 흐름:
  [1] converse(messages + toolConfig) → 모델에 전달
  [2] stopReason="tool_use", toolUse 블록 → 모델이 도구 요청
  [3] 우리 코드 → toolResult 반환
  [4] toolResult 담아 다시 converse → 최종 답변

실행:
  python3 P5_02_tooluse_4step.py
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
print("  Part 5 — Tool Use 4단계 흐름 이해")
print("=" * 60)

# ── get_weather 함수 ─────────────────────────────────────────────
def get_weather(city: str) -> dict:
    """wttr.in에서 날씨 조회 (format=3: 한 줄 요약)."""
    url = f"https://wttr.in/{quote(city)}?format=3"
    try:
        req = Request(url, headers={"User-Agent": "curl/8"})
        with urlopen(req, timeout=10) as resp:
            report = resp.read().decode("utf-8").strip()
        return {"city": city, "report": report}
    except (URLError, HTTPError) as e:
        return {"city": city, "error": f"날씨 조회 실패: {e}"}

# ── toolSpec 정의 ────────────────────────────────────────────────
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

TOOL_CONFIG = {"tools": [WEATHER_TOOL]}

# ─────────────────────────────────────────────────────────────────
print("\n[02] 4단계 흐름 단계별 확인")
print("-" * 60)

# [1] converse + toolConfig
print("\n  [Step 1] converse(messages + toolConfig) 전달")
messages = [{"role": "user", "content": [{"text": "서울 날씨 알려줘?"}]}]
resp = bedrock.converse(
    modelId=MODEL_ID,
    messages=messages,
    toolConfig=TOOL_CONFIG,
    inferenceConfig={"maxTokens": 500},
)
print(f"  → stopReason: {resp['stopReason']}")
print(f"  → content 블록 수: {len(resp['output']['message']['content'])}")

# [2] stopReason = tool_use 확인
print("\n  [Step 2] toolUse 블록 확인")
if resp["stopReason"] != "tool_use":
    print(f"  ⚠️  stopReason={resp['stopReason']} (tool_use 아님 — 도구 불필요 질문)")
else:
    for block in resp["output"]["message"]["content"]:
        if "toolUse" in block:
            tu = block["toolUse"]
            print(f"  → 도구명: {tu['name']}")
            print(f"  → 입력값: {tu['input']}")
            print(f"  → toolUseId: {tu['toolUseId']}")

# [3] 도구 실행 → toolResult 생성
print("\n  [Step 3] 도구 실행 → toolResult 생성")
assistant_msg = resp["output"]["message"]
messages.append(assistant_msg)  # assistant 메시지 히스토리에 추가

tool_results = []
for block in assistant_msg["content"]:
    if "toolUse" in block:
        tu = block["toolUse"]
        result = get_weather(**tu["input"])
        print(f"  → get_weather({tu['input']}) = {result}")
        tool_results.append({
            "toolResult": {
                "toolUseId": tu["toolUseId"],
                "content": [{"json": result}],
            }
        })

# user 메시지에 toolResult 담기
messages.append({"role": "user", "content": tool_results})

# [4] toolResult 담아 다시 converse
print("\n  [Step 4] toolResult 포함 재호출 → 최종 답변")
final = bedrock.converse(
    modelId=MODEL_ID,
    messages=messages,
    toolConfig=TOOL_CONFIG,
    inferenceConfig={"maxTokens": 500},
)
answer = final["output"]["message"]["content"][0]["text"]
print(f"  → stopReason: {final['stopReason']}")
print(f"  → 최종 답변: {answer[:200]}")

print(f"""
  ─────────────────────────────────────────────
  4단계 핵심 포인트:

  [1] toolConfig 포함 → 모델이 도구 존재 인식
  [2] stopReason="tool_use" → 도구 호출 요청 신호
  [3] 우리 코드가 실제 함수 실행 → toolResult 생성
  [4] toolResult 담아 재호출 → 모델이 최종 답변 생성

  ⚠️  주요 오류 주의사항:
  • toolUseId 불일치 → ValidationException
  • roles must alternate → assistant 다음 user(toolResult) 순서 필수
  • toolResult content 형식 → dict: {{"json": ...}}
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P5_02 완료 → P5_03 으로 진행하세요")
print("=" * 60)
