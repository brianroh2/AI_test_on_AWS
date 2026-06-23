# ============================================================
# 파일명: P6_10_strands_react_rewoo_streamlit.py
# 주제: ReAct vs ReWOO 패턴 비교 — Streamlit UI
#
# P6_10_strands_react.py + P6_11_strands_rewoo.py의 시각화 버전
# - ReAct 탭: Thought→Action→Observation 사이클을 카드로 표시
# - ReWOO 탭: Planner 계획표 / Worker 실행 / Solver 답변 3단계 분리
# - 동일 질문으로 두 패턴 비교 가능
#
# 실행:
#   streamlit run P6_10_strands_react_rewoo_streamlit.py \
#     --server.port 8510 --server.headless true &
#   접속: VS Code Ports 탭 → 8510 포워딩
# ============================================================

import streamlit as st
import boto3
import json
import re
import requests
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

st.set_page_config(
    page_title="ReAct vs ReWOO",
    page_icon="🤖",
    layout="wide",
)


# ── Bedrock 모델 ─────────────────────────────────────────────
@st.cache_resource
def get_model(streaming: bool):
    session = boto3.Session(region_name=REGION)
    return BedrockModel(
        model_id=MODEL_ID,
        boto_session=session,
        streaming=streaming,
    )


# ── 공통 도구 정의 ────────────────────────────────────────────
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


# ── ReAct 실행 (Strands 이벤트 수집) ─────────────────────────
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
"""

REWOO_PLANNER_PROMPT = """당신은 ReWOO 패턴의 Planner입니다.

주어진 과제를 분석하여 실행 계획을 JSON 배열로 반환하세요.
도구를 직접 호출하지 말고, 계획만 세우세요.

사용 가능한 도구:
- weather_forecast(city): 도시 날씨 조회
- calculator(expression, mode): 수식 계산 (mode="evaluate")
- web_search(query): 웹 검색

응답 형식 (JSON 배열만 반환, 다른 텍스트 없음):
[
  {"step": 1, "tool": "도구명", "input": {"파라미터": "값"}, "purpose": "이 단계의 목적"},
  {"step": 2, "tool": "도구명", "input": {"파라미터": "값"}, "purpose": "이 단계의 목적"}
]
"""

REWOO_SOLVER_PROMPT = """당신은 ReWOO 패턴의 Solver입니다.
주어진 과제와 각 단계별 실행 결과를 바탕으로 최종 답변을 작성하세요.
결과를 명확하고 간결하게 정리해 주세요.
"""


def run_react(task: str) -> dict:
    """ReAct 에이전트 실행 — 사이클 이벤트 수집"""
    cycles   = []
    cycle    = {}
    full_log = []

    class StepCollector:
        def __call__(self, **kwargs):
            event_loop_metrics = kwargs.get("event_loop_metrics")
            current_tool_use   = kwargs.get("current_tool_use")
            data               = kwargs.get("data", "")

            if current_tool_use and current_tool_use.get("name"):
                cycle["action"] = current_tool_use["name"]
                cycle["action_input"] = current_tool_use.get("input", {})

            if data:
                full_log.append(str(data))

    collector = StepCollector()

    model  = get_model(streaming=True)
    agent  = Agent(
        model=model,
        tools=[weather_forecast, web_search, calculator],
        system_prompt=REACT_SYSTEM_PROMPT,
        callback_handler=collector,
    )

    result = agent(task)
    final  = str(result).strip()

    return {"final_answer": final, "full_log": "".join(full_log)}


def run_rewoo(task: str) -> dict:
    """ReWOO 패턴 실행 — Planner/Worker/Solver 분리"""
    model_ns = get_model(streaming=False)

    # Planner
    planner = Agent(
        model=model_ns,
        system_prompt=REWOO_PLANNER_PROMPT,
        callback_handler=None,
    )
    plan_result = planner(task)
    plan_text   = str(plan_result).strip()

    json_match = re.search(r'\[.*?\]', plan_text, re.DOTALL)
    if json_match:
        plan_text = json_match.group(0)

    try:
        plan = json.loads(plan_text)
    except json.JSONDecodeError:
        plan = [
            {"step": 1, "tool": "weather_forecast", "input": {"city": "Seoul"},  "purpose": "서울 기온 조회"},
            {"step": 2, "tool": "weather_forecast", "input": {"city": "London"}, "purpose": "런던 기온 조회"},
            {"step": 3, "tool": "calculator", "input": {"expression": "평균", "mode": "evaluate"}, "purpose": "평균 계산"},
        ]

    # Worker
    worker = Agent(
        model=model_ns,
        tools=[weather_forecast, calculator, web_search],
        callback_handler=None,
    )
    observations = {}

    for step in plan:
        step_num  = step["step"]
        tool_name = step["tool"]
        inp       = dict(step.get("input", {}))

        if tool_name == "calculator":
            temps = []
            for obs_val in observations.values():
                m = re.search(r':\s*([-\d]+(?:\.\d+)?)°C', obs_val)
                if m:
                    temps.append(float(m.group(1)))
            if len(temps) >= 2:
                inp = {"expression": f"({temps[0]} + {temps[1]}) / 2", "mode": "evaluate"}

        try:
            if tool_name == "weather_forecast":
                raw = worker.tool.weather_forecast(**inp)
            elif tool_name == "calculator":
                raw = worker.tool.calculator(**inp)
            elif tool_name == "web_search":
                raw = worker.tool.web_search(**inp)
            else:
                raw = {"content": [{"text": f"알 수 없는 도구: {tool_name}"}]}
            result_text = raw["content"][0]["text"] if raw.get("content") else str(raw)
        except Exception as e:
            result_text = f"오류: {e}"

        observations[step_num] = result_text

    # Solver
    solver = Agent(
        model=model_ns,
        system_prompt=REWOO_SOLVER_PROMPT,
        callback_handler=None,
    )
    obs_text     = "\n".join(f"Step {k} 결과: {v}" for k, v in observations.items())
    solver_input = f"과제: {task}\n\n실행 결과:\n{obs_text}\n\n위 결과를 종합하여 최종 답변을 작성하세요."
    solver_result = str(solver(solver_input)).strip()

    return {
        "plan":         plan,
        "observations": observations,
        "final_answer": solver_result,
    }


# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"<div style='background:#1a3a2a;border-radius:8px;padding:0.7rem 1rem;"
        f"font-size:0.9rem;color:#e0e0e0;line-height:2;'>"
        f"🤖 <b>ReAct vs ReWOO</b><br>"
        f"🛠 <span style='color:#7ec8e3'>{MODEL_ID.split('.')[-1]}</span><br>"
        f"🌏 <span style='color:#7ec8e3'>{REGION}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("**📌 예시 질문**")
    EXAMPLES = [
        "서울과 런던의 현재 기온을 조회하고 평균을 계산해줘.",
        "도쿄 날씨 확인 후 화씨로 변환해줘. (F = C × 9/5 + 32)",
        "AWS Bedrock 최신 소식 검색하고 요약해줘.",
    ]
    for ex in EXAMPLES:
        if st.button(ex[:30] + "…", key=f"ex_{ex[:10]}", use_container_width=True):
            st.session_state["preset"] = ex

    st.markdown("---")
    st.markdown("""
**패턴 비교**

| | ReAct | ReWOO |
|---|---|---|
| 계획 | 즉흥적 | 사전 수립 |
| 도구 | 반응형 | 순서대로 |
| 수정 | 가능 | 제한적 |
| 적합 | 탐색형 | 구조화형 |
    """)


# ── 메인 ─────────────────────────────────────────────────────
st.title("🤖 ReAct vs ReWOO 패턴 비교")
st.caption(f"모델: `{MODEL_ID}` | 동일 질문으로 두 패턴의 실행 방식 비교")

if "preset" not in st.session_state:
    st.session_state["preset"] = ""

task_input = st.text_input(
    "질문 / 과제",
    value=st.session_state["preset"] or "서울과 런던의 현재 기온을 조회하고 평균을 계산해줘.",
    placeholder="에이전트에게 실행할 과제를 입력하세요...",
)
st.session_state["preset"] = ""

col1, col2 = st.columns(2)
run_react_btn = col1.button("▶ ReAct 실행",  type="primary",   use_container_width=True)
run_rewoo_btn = col2.button("▶ ReWOO 실행",  type="secondary", use_container_width=True)

st.markdown("---")

# ── ReAct 탭 / ReWOO 탭 ──────────────────────────────────────
tab_react, tab_rewoo, tab_compare = st.tabs(["🔄 ReAct", "📋 ReWOO", "⚖️ 패턴 비교"])

with tab_react:
    st.subheader("🔄 ReAct — Reason + Act 반복")
    st.markdown("""
> **Thought → Action → Observation** 사이클을 반복하며 점진적으로 문제를 해결합니다.
> 결과를 보면서 다음 행동을 즉흥적으로 결정하는 **반응형** 패턴입니다.
    """)

    if run_react_btn and task_input.strip():
        with st.spinner("ReAct 에이전트 실행 중..."):
            react_result = run_react(task_input.strip())
            st.session_state["react_result"] = react_result

    if "react_result" in st.session_state:
        r = st.session_state["react_result"]

        st.success("✅ ReAct 실행 완료")
        st.markdown("**📝 최종 답변**")
        st.info(r["final_answer"])

        if r.get("full_log"):
            with st.expander("🔍 전체 실행 로그"):
                st.text(r["full_log"][:3000])
    else:
        st.info("위에서 과제를 입력하고 'ReAct 실행' 버튼을 누르세요.")


with tab_rewoo:
    st.subheader("📋 ReWOO — Planner → Worker → Solver")
    st.markdown("""
> **전체 계획을 먼저 수립**한 뒤 Worker가 순서대로 실행합니다.
> 구조화된 과제에 효율적인 **계획형** 패턴입니다.
    """)

    if run_rewoo_btn and task_input.strip():
        with st.spinner("ReWOO 에이전트 실행 중..."):
            rewoo_result = run_rewoo(task_input.strip())
            st.session_state["rewoo_result"] = rewoo_result

    if "rewoo_result" in st.session_state:
        r = st.session_state["rewoo_result"]

        # Planner 계획
        st.markdown("### 1️⃣ Planner — 실행 계획")
        for step in r["plan"]:
            with st.container():
                st.markdown(
                    f"<div style='border-left:4px solid #4a9eff;padding:0.5rem 1rem;"
                    f"background:#0e1a2e;border-radius:4px;margin-bottom:0.5rem;'>"
                    f"<b>Step {step['step']}</b> — <code>{step['tool']}</code><br>"
                    f"<span style='color:#aaa;font-size:0.9rem;'>목적: {step.get('purpose','')}</span><br>"
                    f"<span style='color:#7ec8e3;font-size:0.85rem;'>입력: {json.dumps(step.get('input',{}), ensure_ascii=False)}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # Worker 결과
        st.markdown("### 2️⃣ Worker — 도구 실행 결과")
        for step_num, obs in r["observations"].items():
            step_info = next((s for s in r["plan"] if s["step"] == step_num), {})
            st.markdown(
                f"<div style='border-left:4px solid #2ecc71;padding:0.5rem 1rem;"
                f"background:#0e2a1e;border-radius:4px;margin-bottom:0.5rem;'>"
                f"<b>Step {step_num}</b> [{step_info.get('tool','')}]<br>"
                f"<span style='color:#90ee90;'>{obs}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # Solver 최종 답변
        st.markdown("### 3️⃣ Solver — 최종 답변")
        st.success(r["final_answer"])
    else:
        st.info("위에서 과제를 입력하고 'ReWOO 실행' 버튼을 누르세요.")


with tab_compare:
    st.subheader("⚖️ ReAct vs ReWOO 개념 비교")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("""
### 🔄 ReAct
```
질문
  ↓
Thought (추론)
  ↓
Action (도구 선택)
  ↓
Observation (결과 확인)
  ↓ (반복)
Final Answer
```
**특징**
- 결과 보면서 즉흥적으로 다음 행동 결정
- 탐색적·개방형 문제에 강함
- 중간에 계획 변경 가능
- API 호출 횟수가 유동적

**적합한 상황**
- 결과를 봐야 다음 단계를 알 수 있는 경우
- 탐색적 리서치
        """)

    with col_b:
        st.markdown("""
### 📋 ReWOO
```
질문
  ↓
Planner (전체 계획 수립)
  ↓
Worker Step 1
  ↓
Worker Step 2
  ↓
  ...
  ↓
Solver (결과 종합)
```
**특징**
- 전체 계획을 미리 수립 후 순서대로 실행
- 구조화된 반복 작업에 강함
- LLM 호출 횟수 예측 가능
- Planner/Worker/Solver 역할 분리

**적합한 상황**
- 단계가 명확히 정해진 경우
- 병렬 실행 가능한 독립 작업
        """)

    st.markdown("---")
    st.markdown("""
| 비교 항목 | ReAct | ReWOO |
|-----------|-------|-------|
| 계획 시점 | 실행 중 즉흥 | 시작 전 전체 수립 |
| 유연성 | 높음 | 낮음 |
| 예측 가능성 | 낮음 | 높음 |
| 토큰 효율 | 낮음 (반복 추론) | 높음 (계획 분리) |
| 적합 문제 | 탐색·조사형 | 구조화·반복형 |
    """)
