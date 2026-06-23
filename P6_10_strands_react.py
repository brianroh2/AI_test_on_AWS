"""
P6_10_strands_react.py
────────────────────────────────────────────────────────────────────
Strands 챕터 10 — ReAct Agent

ReAct 패턴: Reason → Act → Observe 반복
  • weather_forecast (wttr.in)
  • web_search (DuckDuckGo)
  • calculator (strands_tools)

10-1. ReAct system_prompt 정의
10-2. ReAct Agent 생성
10-3. 복합 질문 실행 — 날씨 + 검색 + 계산

실행:
  python3 P6_10_strands_react.py
────────────────────────────────────────────────────────────────────
"""

import requests
import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

session = boto3.Session(region_name=REGION)

model = BedrockModel(
    model_id=MODEL_ID,
    boto_session=session,
    streaming=True,
)

print("=" * 60)
print("  Part 6 — ReAct Agent")
print("=" * 60)

# ── 도구 정의 ────────────────────────────────────────────────────

@tool
def weather_forecast(city: str) -> str:
    """지정한 도시의 현재 날씨를 조회한다.

    Args:
        city: 날씨를 조회할 도시 이름 (영문). 예: Seoul, Tokyo, London
    """
    try:
        resp = requests.get(f"https://wttr.in/{city}?format=j1", timeout=5)
        resp.raise_for_status()
        cc = resp.json()["current_condition"][0]
        return (
            f"{city}: {cc['weatherDesc'][0]['value']}, "
            f"{cc['temp_C']}°C, 습도 {cc['humidity']}%"
        )
    except Exception as e:
        return f"날씨 조회 실패 ({city}): {e}"


@tool
def web_search(query: str, max_results: int = 3) -> str:
    """DuckDuckGo로 웹 검색을 수행한다.

    Args:
        query: 검색할 키워드 또는 문장
        max_results: 반환할 최대 결과 수 (기본값 3)
    """
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return f"'{query}' 검색 결과 없음"
        return "\n".join(
            f"{i+1}. {r['title']} — {r['href']}" for i, r in enumerate(results)
        )
    except Exception as e:
        return f"검색 실패: {e}"


# ── 10-1. ReAct system_prompt ────────────────────────────────────
print("\n[10-1] ReAct system_prompt 정의")

REACT_SYSTEM_PROMPT = """당신은 ReAct(Reasoning + Acting) 패턴으로 동작하는 AI 에이전트입니다.

## ReAct 단계
1. **Thought** (추론): 문제를 분석하고 다음 행동을 계획합니다.
2. **Action** (행동): 적절한 도구를 선택하여 실행합니다.
3. **Observation** (관찰): 도구 실행 결과를 확인합니다.
4. 위 단계를 필요한 만큼 반복합니다.
5. **Final Answer**: 수집된 정보를 종합하여 최종 답변을 제공합니다.

## 원칙
- 사실에 기반한 답변만 제공합니다.
- 도구 결과를 그대로 신뢰하고 인용합니다.
- 계산이 필요하면 반드시 calculator 도구를 사용합니다.
- 정보가 부족하면 추가 도구 호출로 보완합니다.
"""

print("  ReAct system_prompt 설정 완료")
print(f"  포함 단계: Thought → Action → Observation → Final Answer")

# ── 10-2. ReAct Agent 생성 ───────────────────────────────────────
print("\n[10-2] ReAct Agent 생성")

react_agent = Agent(
    model=model,
    tools=[weather_forecast, web_search, calculator],
    system_prompt=REACT_SYSTEM_PROMPT,
)

print(f"  등록된 도구: weather_forecast, web_search, calculator")

# ── 10-3. 복합 질문 실행 ─────────────────────────────────────────
print("\n[10-3] 복합 질문 실행")
print("-" * 40)

react_agent(
    "다음 세 가지를 순서대로 처리해줘:\n"
    "1. 서울의 현재 기온을 확인해줘.\n"
    "2. 서울 기온을 화씨(°F)로 변환해줘. (공식: F = C × 9/5 + 32)\n"
    "3. AWS Bedrock 관련 최신 소식을 1건 검색해줘.\n"
    "모든 결과를 마지막에 종합해서 정리해줘."
)

print(f"""
  ─────────────────────────────────────────────
  ReAct 패턴 핵심:
    Thought  → 문제 분석 및 행동 계획
    Action   → 도구 선택 및 실행
    Observation → 도구 결과 확인
    (반복)   → 정보 충분할 때까지
    Final Answer → 종합 답변

  구현 포인트:
    • system_prompt 에 ReAct 단계 명시
    • 복합 도구(날씨 + 검색 + 계산)를 함께 등록
    • Agent 가 자율적으로 단계 반복 결정

  ⚠️  주의:
    • max_turns 기본값(10)으로 무한 루프 방지
    • 도구 오류 시 Agent 가 대안 도구로 재시도 가능
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P6_10 완료 → P6_11 로 진행하세요")
print("=" * 60)
