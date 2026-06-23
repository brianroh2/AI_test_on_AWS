"""
P6_08_strands_custom_tool.py
────────────────────────────────────────────────────────────────────
Strands 챕터 08 — 사용자 정의 도구 (@tool 데코레이터)

08-1. @tool 기본 — weather_forecast (wttr.in JSON API)
08-2. @tool 심화 — web_search (duckduckgo_search)
08-3. @tool 단순 — random_float / random_string
08-4. 다중 사용자 도구 Agent
08-5. agent.tool.xxx 직접 호출

실행:
  python3 P6_08_strands_custom_tool.py
────────────────────────────────────────────────────────────────────
"""

import os
import random
import string
import requests
import boto3
from strands import Agent, tool
from strands.models import BedrockModel

os.environ["BYPASS_TOOL_CONSENT"] = "true"

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

session = boto3.Session(region_name=REGION)

model = BedrockModel(
    model_id=MODEL_ID,
    boto_session=session,
    streaming=True,
)

print("=" * 60)
print("  Part 6 — 사용자 정의 도구 (@tool 데코레이터)")
print("=" * 60)

# ── 사용자 정의 도구 정의 ────────────────────────────────────────

@tool
def weather_forecast(city: str) -> str:
    """지정한 도시의 현재 날씨를 wttr.in JSON API로 조회한다.

    Args:
        city: 날씨를 조회할 도시 이름 (영문). 예: Seoul, Tokyo, London
    """
    try:
        url = f"https://wttr.in/{city}?format=j1"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        cc = resp.json()["current_condition"][0]
        return (
            f"{city} 날씨: {cc['weatherDesc'][0]['value']}, "
            f"기온 {cc['temp_C']}°C, 습도 {cc['humidity']}%"
        )
    except Exception as e:
        return f"날씨 조회 실패 ({city}): {e}"


@tool
def web_search(query: str, max_results: int = 3) -> str:
    """DuckDuckGo를 사용해 웹 검색을 수행하고 결과를 반환한다.

    Args:
        query: 검색할 키워드 또는 문장
        max_results: 반환할 최대 결과 수 (기본값 3)
    """
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return f"'{query}' 검색 결과 없음"
        lines = [f"{i+1}. {r['title']} — {r['href']}" for i, r in enumerate(results)]
        return "\n".join(lines)
    except Exception as e:
        return f"검색 실패: {e}"


@tool
def random_float(min_val: float = 0.0, max_val: float = 1.0) -> float:
    """지정된 범위 내에서 랜덤 실수를 생성한다.

    Args:
        min_val: 최솟값 (기본값 0.0)
        max_val: 최댓값 (기본값 1.0)
    """
    return round(random.uniform(min_val, max_val), 4)


@tool
def random_string(length: int = 8) -> str:
    """알파벳 대소문자와 숫자로 이루어진 랜덤 문자열을 생성한다.

    Args:
        length: 생성할 문자열 길이 (기본값 8)
    """
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


# ── 08-1. weather_forecast ───────────────────────────────────────
print("\n[08-1] @tool — weather_forecast (wttr.in JSON API)")

agent_weather = Agent(model=model, tools=[weather_forecast])
agent_weather("서울과 도쿄의 현재 날씨를 비교해줘")

# ── 08-2. web_search ─────────────────────────────────────────────
print("\n\n[08-2] @tool — web_search (DuckDuckGo)")

agent_search = Agent(model=model, tools=[web_search])
agent_search("Amazon Bedrock strands agents 최신 소식을 검색해줘")

# ── 08-3. random_float / random_string ───────────────────────────
print("\n\n[08-3] @tool — random_float / random_string")

agent_rand = Agent(model=model, tools=[random_float, random_string])
agent_rand("0~100 사이 랜덤 숫자 3개와 길이 12의 랜덤 문자열 2개를 생성해줘")

# ── 08-4. 다중 도구 Agent ─────────────────────────────────────────
print("\n\n[08-4] 다중 사용자 도구 Agent")

multi_agent = Agent(
    model=model,
    tools=[weather_forecast, web_search, random_float, random_string],
    system_prompt="당신은 다양한 도구를 활용하는 멀티 에이전트입니다. 필요한 도구를 적절히 선택해 사용합니다.",
)

multi_agent("서울 날씨를 알려주고, AWS Bedrock 관련 최신 뉴스 2건을 검색해줘")

# ── 08-5. agent.tool.xxx 직접 호출 ───────────────────────────────
print("\n\n[08-5] agent.tool.xxx — 사용자 도구 직접 호출")

direct_agent = Agent(
    model=model,
    tools=[weather_forecast, random_string],
    callback_handler=None,
)

w = direct_agent.tool.weather_forecast(city="London")
print(f"  weather_forecast(London) → {w['content'][0]['text']}")

r = direct_agent.tool.random_string(length=10)
print(f"  random_string(10)        → {r['content'][0]['text']}")

print(f"""
  ─────────────────────────────────────────────
  @tool 데코레이터 핵심:
    • @tool 로 일반 함수를 Strands 도구로 변환
    • 함수 docstring → 도구 설명 (LLM이 선택 기준으로 활용)
    • 타입 힌트 → 도구 입력 스키마 자동 생성
    • Agent(tools=[my_tool]) 로 등록

  agent.tool.xxx 직접 호출:
    • agent.tool.weather_forecast(city="Seoul")
    • 반환값: {{'status': ..., 'content': [{{'text': ...}}]}}

  ⚠️  주의:
    • docstring의 Args: 섹션은 LLM에 노출되므로 명확히 작성
    • 도구 함수에서 예외 처리 필수 (네트워크 오류 등)
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P6_08 완료 → P6_09 로 진행하세요")
print("=" * 60)
