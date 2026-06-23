"""
P5_05_tooluse_multi.py
────────────────────────────────────────────────────────────────────
Tool Use 챕터 05 — 다중 도구 (get_weather + get_time)

05-1. get_time 함수 구현 (datetime + zoneinfo)
05-2. TIME_TOOL toolSpec 정의
05-3. run_conversation() — tool_use 반복 처리
05-4. 테스트 (날씨+시간 복합 질문)

실행:
  python3 P5_05_tooluse_multi.py
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
print("  Part 5 — 다중 도구 사용 (날씨 + 시간)")
print("=" * 60)

# ── get_weather ──────────────────────────────────────────────────
def get_weather(city: str) -> dict:
    url = f"https://wttr.in/{quote(city)}?format=3"
    try:
        req = Request(url, headers={"User-Agent": "curl/8"})
        with urlopen(req, timeout=10) as resp:
            report = resp.read().decode("utf-8").strip()
        return {"city": city, "report": report}
    except (URLError, HTTPError) as e:
        return {"city": city, "error": f"날씨 조회 실패: {e}"}

# ── 05-1. get_time ───────────────────────────────────────────────
_CITY_TZ = {
    "서울": "Asia/Seoul", "Seoul": "Asia/Seoul",
    "도쿄": "Asia/Tokyo", "Tokyo": "Asia/Tokyo",
    "뉴욕": "America/New_York", "New York": "America/New_York",
    "런던": "Europe/London", "London": "Europe/London",
}

def get_time(city: str) -> dict:
    """도시의 현재 시간을 반환 (시간대 기반)."""
    tz = _CITY_TZ.get(city)
    if tz is None:
        return {"city": city, "error": "지원하지 않는 도시입니다"}
    now = datetime.now(ZoneInfo(tz))
    return {
        "city": city,
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": ["월", "화", "수", "목", "금", "토", "일"][now.weekday()],
    }

print("\n[05-1] get_time 함수 동작 확인")
print(get_time("서울"))
print(get_time("뉴욕"))

# ── 05-2. toolSpec 정의 ──────────────────────────────────────────
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

TIME_TOOL = {
    "toolSpec": {
        "name": "get_time",
        "description": "도시의 현재 날짜와 시간을 반환합니다. 한글 또는 영문 도시명을 사용합니다.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "도시명. 예: 서울, 도쿄, 뉴욕, 런던"}
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

# ── 05-3. run_conversation() — tool_use 반복 처리 ────────────────
def run_conversation(messages: list, max_turns: int = 5) -> str:
    """tool_use가 반복되는 경우도 처리."""
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

    return "[ max_turns 초과 — 응답 없음 ]"

def ask(user_text: str) -> str:
    return run_conversation([{"role": "user", "content": [{"text": user_text}]}])

# ── 05-4. 테스트 ─────────────────────────────────────────────────
print("\n[05-4] 다중 도구 테스트")

tests = [
    ("A1", "서울 지금 몇 시야?"),
    ("A2", "도쿄 날씨 알려줘"),
    ("A3", "서울 지금 시간이랑 날씨 둘 다 알려줘"),
]

for label, q in tests:
    print(f"\n  {label}: {q}")
    ans = ask(q)
    print(f"  → {ans[:150]}")

print(f"""
  ─────────────────────────────────────────────
  (참고) toolChoice 옵션:
    auto (기본) : 모델이 도구 사용 여부 판단
    any         : 반드시 도구 1개 이상 사용
    tool        : 특정 도구만 강제 호출

  TOOL_CONFIG_FORCED = {{
    "tools": [WEATHER_TOOL, TIME_TOOL],
    "toolChoice": {{"any": {{}}}}
  }}

  ⚠️  주의:
    zoneinfo 없으면 Python 3.8 이하 → pip install tzdata
    max_turns 초과 시 "[ max_turns 초과 ]" 반환
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P5_05 완료 → P5_06 으로 진행하세요")
print("=" * 60)
