"""
P6_11_strands_rewoo.py
────────────────────────────────────────────────────────────────────
Strands 챕터 11 — ReWOO Agent

ReWOO 패턴: Planner → Worker → Solver
  1. Planner: 전체 계획을 한 번에 수립 (도구 호출 없음)
  2. Worker:  계획에 따라 도구를 순서대로 실행
  3. Solver:  결과를 종합하여 최종 답변 생성

11-1. Planner Agent — 계획 수립
11-2. Worker 실행 — 계획에 따라 도구 호출
11-3. Solver Agent — 최종 답변 생성

실행:
  python3 P6_11_strands_rewoo.py
────────────────────────────────────────────────────────────────────
"""

import json
import re
import requests
import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

session = boto3.Session(region_name=REGION)

model_ns = BedrockModel(
    model_id=MODEL_ID,
    boto_session=session,
    streaming=False,
)

print("=" * 60)
print("  Part 6 — ReWOO Agent")
print("=" * 60)

# ── 도구 정의 ────────────────────────────────────────────────────

@tool
def weather_forecast(city: str) -> str:
    """지정한 도시의 현재 날씨를 조회한다.

    Args:
        city: 날씨를 조회할 도시 이름 (영문)
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
        return f"날씨 조회 실패: {e}"


# ── 11-1. Planner Agent ──────────────────────────────────────────
print("\n[11-1] Planner Agent — 계획 수립")

PLANNER_PROMPT = """당신은 ReWOO 패턴의 Planner입니다.

주어진 과제를 분석하여 실행 계획을 JSON 배열로 반환하세요.
도구를 직접 호출하지 말고, 계획만 세우세요.

사용 가능한 도구:
- weather_forecast(city): 도시 날씨 조회
- calculator(expression, mode): 수식 계산 (mode="evaluate")

응답 형식 (JSON 배열만 반환, 다른 텍스트 없음):
[
  {"step": 1, "tool": "도구명", "input": {"파라미터": "값"}, "purpose": "이 단계의 목적"},
  {"step": 2, "tool": "도구명", "input": {"파라미터": "값"}, "purpose": "이 단계의 목적"}
]
"""

planner = Agent(
    model=model_ns,
    system_prompt=PLANNER_PROMPT,
    callback_handler=None,
)

TASK = (
    "서울과 런던의 현재 기온을 조회한 뒤, "
    "두 도시 기온의 평균을 계산해줘."
)

print(f"  과제: {TASK}")
print()

plan_result = planner(TASK)
plan_text = str(plan_result).strip()

# JSON 배열 추출
json_match = re.search(r'\[.*?\]', plan_text, re.DOTALL)
if json_match:
    plan_text = json_match.group(0)

try:
    plan = json.loads(plan_text)
except json.JSONDecodeError:
    plan = [
        {"step": 1, "tool": "weather_forecast", "input": {"city": "Seoul"},  "purpose": "서울 기온 조회"},
        {"step": 2, "tool": "weather_forecast", "input": {"city": "London"}, "purpose": "런던 기온 조회"},
        {"step": 3, "tool": "calculator",       "input": {"expression": "(서울기온 + 런던기온) / 2", "mode": "evaluate"}, "purpose": "평균 기온 계산"},
    ]

print("  수립된 계획:")
for step in plan:
    print(f"  Step {step['step']}: [{step['tool']}] {step.get('purpose', '')}")

# ── 11-2. Worker — 계획 실행 ─────────────────────────────────────
print("\n[11-2] Worker — 계획에 따라 도구 실행")

worker_agent = Agent(
    model=model_ns,
    tools=[weather_forecast, calculator],
    callback_handler=None,
)

observations = {}

for step in plan:
    step_num  = step["step"]
    tool_name = step["tool"]
    inp       = step.get("input", {})
    purpose   = step.get("purpose", "")

    # 이전 결과에서 기온 값 대입 (calculator 단계)
    if tool_name == "calculator":
        expr = inp.get("expression", "")
        for obs_key, obs_val in observations.items():
            temp_match = re.search(r'(\d+(?:\.\d+)?)°C', obs_val)
            if temp_match:
                placeholder = f"도시{obs_key}기온"
                expr = expr.replace(placeholder, temp_match.group(1))
        # 기온 숫자만 추출해서 평균 수식 직접 계산
        temps = []
        for obs_val in observations.values():
            m = re.search(r':\s*([-\d]+(?:\.\d+)?)°C', obs_val)
            if m:
                temps.append(float(m.group(1)))
        if len(temps) == 2:
            expr = f"({temps[0]} + {temps[1]}) / 2"
        inp = {"expression": expr, "mode": "evaluate"}

    # 도구 직접 호출
    if tool_name == "weather_forecast":
        raw = worker_agent.tool.weather_forecast(**inp)
    elif tool_name == "calculator":
        raw = worker_agent.tool.calculator(**inp)
    else:
        raw = {"content": [{"text": f"알 수 없는 도구: {tool_name}"}]}

    result_text = raw["content"][0]["text"] if raw.get("content") else str(raw)
    observations[step_num] = result_text
    print(f"  Step {step_num} [{tool_name}]: {result_text}")

# ── 11-3. Solver Agent ────────────────────────────────────────────
print("\n[11-3] Solver Agent — 최종 답변 생성")

SOLVER_PROMPT = """당신은 ReWOO 패턴의 Solver입니다.
주어진 과제와 각 단계별 실행 결과를 바탕으로 최종 답변을 작성하세요.
결과를 명확하고 간결하게 정리해 주세요.
"""

solver = Agent(
    model=model_ns,
    system_prompt=SOLVER_PROMPT,
)

obs_text = "\n".join(
    f"Step {k} 결과: {v}" for k, v in observations.items()
)

solver_input = f"""과제: {TASK}

실행 결과:
{obs_text}

위 결과를 종합하여 최종 답변을 작성하세요."""

print()
solver(solver_input)

print(f"""
  ─────────────────────────────────────────────
  ReWOO 패턴 핵심:

  ① Planner (도구 미사용)
      - 과제를 분석해 JSON 실행 계획 수립
      - 도구 호출 없이 순수 추론만 수행

  ② Worker (도구 직접 실행)
      - 계획의 각 Step 을 순서대로 실행
      - 이전 단계 결과를 다음 단계 입력에 활용

  ③ Solver (결과 종합)
      - 모든 관찰 결과를 받아 최종 답변 생성

  ReAct vs ReWOO:
    ReAct  → 매 Action 후 즉시 Observe → 반응적
    ReWOO  → 전체 계획 먼저 수립 → 효율적
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P6_11 완료 — Part 6 전체 완료!")
print("=" * 60)
