"""
P5_03_tooluse_tooluse.py
────────────────────────────────────────────────────────────────────
Tool Use 챕터 03 — get_weather 도구 정의 + toolUse 응답 파싱

03-1. get_weather 함수 구현 (wttr.in)
03-2. toolSpec 정의
03-3. toolConfig 로 converse 호출
03-4. toolUse 블록 파싱

실행:
  python3 P5_03_tooluse_tooluse.py
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
print("  Part 5 — 도구 정의 및 toolUse 응답 파싱")
print("=" * 60)

# ── 03-1. get_weather 함수 ───────────────────────────────────────
print("\n[03-1] get_weather 함수 동작 확인")

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

print(get_weather("Seoul"))
print(get_weather("Tokyo"))

# ── 03-2. toolSpec 정의 ──────────────────────────────────────────
print("\n[03-2] toolSpec 정의")

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
print(f"  도구명: {WEATHER_TOOL['toolSpec']['name']}")
print(f"  inputSchema required: {WEATHER_TOOL['toolSpec']['inputSchema']['json']['required']}")

# ── 03-3. toolConfig로 converse 호출 ─────────────────────────────
print("\n[03-3] toolConfig 포함 converse 호출")

resp = bedrock.converse(
    modelId=MODEL_ID,
    messages=[{"role": "user", "content": [{"text": "서울 날씨 알려줘?"}]}],
    toolConfig={"tools": [WEATHER_TOOL]},
    inferenceConfig={"maxTokens": 500},
)
print(f"  stopReason: {resp['stopReason']}")
print(f"  content 블록 수: {len(resp['output']['message']['content'])}")

# ── 03-4. toolUse 블록 파싱 ──────────────────────────────────────
print("\n[03-4] toolUse 블록 파싱")
for block in resp["output"]["message"]["content"]:
    if "toolUse" in block:
        tu = block["toolUse"]
        print(f"  도구명 : {tu['name']}")
        print(f"  입력값 : {tu['input']}")
        print(f"  ID     : {tu['toolUseId']}")
        # get_weather 호출
        city = tu["input"].get("city", "Seoul")
        result = get_weather(city)
        print(f"  실행결과: {result}")

print(f"""
  ─────────────────────────────────────────────
  도구 정의 3요소 (toolSpec):
    name        : 모델이 호출할 도구 이름 (영문)
    description : 언제/왜 쓰는지 + 반환값 설명 (중요!)
    inputSchema : 파라미터 구조 (JSON Schema)

  ⚠️  주요 오류:
    inputSchema ValidationException
      → {{"json": {{...}}}} 형식 필수
    toolConfig ValidationException
      → {{"tools": [WEATHER_TOOL]}} 형식 필수
    stopReason end_turn (도구 미호출)
      → description이 불명확할 때 발생
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P5_03 완료 → P5_04 로 진행하세요")
print("=" * 60)
