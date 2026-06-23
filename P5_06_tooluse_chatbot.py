"""
P5_06_tooluse_chatbot.py
────────────────────────────────────────────────────────────────────
Tool Use 챕터 06 — 대화 히스토리 + Tool Use 챗봇
                    (+ 선택: Bedrock Mantle 방식 비교)

06-1. chat_turn() — 대화 히스토리 유지
06-2. 대화 히스토리 + Tool Use 테스트
(선택) 06-3. Bedrock Mantle 방식 비교 참고

run_conversation() 함수가 messages 리스트를 유지하면서
toolUse/toolResult 도 히스토리에 포함됩니다.

실행:
  python3 P5_06_tooluse_chatbot.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)

print("=" * 60)
print("  Part 5 — 대화 히스토리 + Tool Use 챗봇")
print("=" * 60)

# ── 도구 함수 ────────────────────────────────────────────────────
def get_weather(city: str) -> dict:
    url = f"https://wttr.in/{quote(city)}?format=3"
    try:
        req = Request(url, headers={"User-Agent": "curl/8"})
        with urlopen(req, timeout=10) as resp:
            report = resp.read().decode("utf-8").strip()
        return {"city": city, "report": report}
    except (URLError, HTTPError) as e:
        return {"city": city, "error": f"날씨 조회 실패: {e}"}

_CITY_TZ = {
    "서울": "Asia/Seoul", "Seoul": "Asia/Seoul",
    "도쿄": "Asia/Tokyo", "Tokyo": "Asia/Tokyo",
    "뉴욕": "America/New_York", "New York": "America/New_York",
    "런던": "Europe/London", "London": "Europe/London",
}

def get_time(city: str) -> dict:
    tz = _CITY_TZ.get(city)
    if tz is None:
        return {"city": city, "error": "지원하지 않는 도시입니다"}
    now = datetime.now(ZoneInfo(tz))
    return {
        "city": city,
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": ["월", "화", "수", "목", "금", "토", "일"][now.weekday()],
    }

WEATHER_TOOL = {
    "toolSpec": {
        "name": "get_weather",
        "description": "도시의 현재 날씨를 조회합니다. 도시명은 영문으로 입력합니다.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "도시명. 예: Seoul, Tokyo"}
                },
                "required": ["city"],
            }
        },
    }
}

TIME_TOOL = {
    "toolSpec": {
        "name": "get_time",
        "description": "도시의 현재 날짜와 시간을 반환합니다.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "도시명. 예: 서울, 도쿄, 뉴욕"}
                },
                "required": ["city"],
            }
        },
    }
}

TOOL_FUNCTIONS = {"get_weather": get_weather, "get_time": get_time}
TOOL_CONFIG    = {"tools": [WEATHER_TOOL, TIME_TOOL]}

# ── run_tool ─────────────────────────────────────────────────────
def run_tool(tool_use: dict) -> dict:
    func   = TOOL_FUNCTIONS.get(tool_use["name"])
    result = func(**tool_use["input"]) if func else {"error": "알 수 없는 도구"}
    return {
        "toolResult": {
            "toolUseId": tool_use["toolUseId"],
            "content": [{"json": result}],
        }
    }

# ── run_conversation() ───────────────────────────────────────────
def run_conversation(messages: list, max_turns: int = 5) -> str:
    """tool_use 반복 처리 + conversation 히스토리 유지."""
    for _ in range(max_turns):
        resp = bedrock.converse(
            modelId=MODEL_ID,
            messages=messages,
            toolConfig=TOOL_CONFIG,
            inferenceConfig={"maxTokens": 600},
        )
        assistant_msg = resp["output"]["message"]
        messages.append(assistant_msg)

        if resp["stopReason"] != "tool_use":
            return assistant_msg["content"][-1]["text"]

        tool_results = []
        for block in assistant_msg["content"]:
            if "toolUse" in block:
                print(f"  [ 도구 호출 ] {block['toolUse']['name']}({block['toolUse']['input']})")
                tool_results.append(run_tool(block["toolUse"]))
        messages.append({"role": "user", "content": tool_results})

    return "[ max_turns 초과 ]"

# ── 06-1. chat_turn() ────────────────────────────────────────────
def chat_turn(conversation: list, user_text: str) -> str:
    """conversation 리스트에 user 메시지 추가 후 응답 반환."""
    conversation.append({"role": "user", "content": [{"text": user_text}]})
    return run_conversation(conversation)  # conversation을 직접 수정

# ── 06-2. 대화 히스토리 + Tool Use 테스트 ────────────────────────
print("\n[06-2] 대화 히스토리 유지 테스트")

conversation = []

q1 = "서울 날씨 어때?"
print(f"\n  질문: {q1}")
r1 = chat_turn(conversation, q1)
print(f"  답변: {r1[:120]}")

q2 = "거기 지금 몇 시야?"
print(f"\n  질문: {q2}")
r2 = chat_turn(conversation, q2)
print(f"  답변: {r2[:120]}")

print(f"\n  history 길이: {len(conversation)} 개 메시지")
print(f"  (user+assistant+toolUse+toolResult 모두 포함)")

# ── (선택) 06-3. Bedrock Mantle 비교 참고 ────────────────────────
print(f"""
  ─────────────────────────────────────────────
  (선택) 06-3. Bedrock Mantle (AnthropicBedrock) 비교

  구분          Converse API          Mantle (Anthropic SDK)
  ─────────────────────────────────────────────────────────
  toolConfig    toolSpec 구조         tools 딕셔너리 구조
  inputSchema   {{"json": {{...}}}}      input_schema=...
  stopReason    "tool_use"            stop_reason="tool_use"
  도구 결과      toolUse/toolResult    tool_use/tool_result
  content 직렬화 dict → json 블록     json.dumps(result, ...)
  ─────────────────────────────────────────────────────────
  conversation history 관리: Chapter1 06 trimming 참고

  이 파일은 Bedrock Converse API 방식으로 구현되었습니다.
  Mantle 방식은 교재 06-3 참고.
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P5_06 완료 → Part 6 (Strands Agents) 으로 진행하세요")
print("=" * 60)
