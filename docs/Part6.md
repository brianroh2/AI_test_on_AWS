# Part 6 — Strands Agentic AI 학습 가이드

## 개요
Strands SDK는 AWS가 만든 **오픈소스 에이전트 프레임워크**입니다.
P5에서 수동으로 구현한 Tool Use 루프, 세션 관리, 멀티에이전트 패턴을
선언적으로 구성할 수 있습니다.

---

## AWS 브라우저(콘솔)에서 확인할 부분

| 확인 항목 | 경로 | 무엇을 보는가 |
|-----------|------|--------------|
| Bedrock 모델 목록 | Bedrock → Models | Strands에 사용할 모델 ID 확인 |
| 호출 로그 | CloudWatch → `/aws/bedrock/` | Strands Agent의 실제 API 호출 추적 |
| 비용 모니터링 | Cost Explorer → Bedrock 필터 | 에이전트 실행당 토큰 비용 확인 |
| MCP 서버 (P6_09) | 로컬 프로세스 — 콘솔 해당 없음 | `ps aux | grep python` 으로 확인 |

---

## 파일별 핵심 내용 및 연관성

```
P6_01_strands_setup.py
  └─ Strands 설치 확인 + BedrockModel 초기 연결 검증

P6_02_strands_agent.py             ← 핵심 시작점
  └─ Agent(model, tools, system_prompt) 기본 패턴
  └─ 이후 모든 P6 파일의 기반

P6_03_strands_system_prompt.py
  └─ system_prompt로 에이전트 역할/규칙/출력 형식 제어

P6_04_strands_memory.py
  └─ Agent(messages=[...]) — 이전 대화 컨텍스트 유지
  └─ messages 리스트 직접 관리

P6_05_strands_session.py          ← 핵심
  └─ JSON 파일로 대화 세션 저장/복원 (FileSessionManager 대체)
  └─ 실제 서비스의 "사용자별 대화 이력 유지" 패턴

P6_06_strands_stat.py
  └─ result.metrics.accumulated_usage — 토큰 사용량 추적
  └─ result.metrics.cycle_durations — 실행 시간 측정
  └─ result.metrics.tool_metrics — 도구별 호출 통계

P6_07_strands_tools.py
  └─ strands_tools 내장 도구: calculator, http_request, file_read, current_time
  └─ agent.tool.xxx() 직접 호출 패턴
  └─ BYPASS_TOOL_CONSENT 환경변수

P6_08_strands_custom_tool.py      ← 핵심
  └─ @tool 데코레이터 — docstring → 설명, 타입힌트 → 스키마 자동 생성

P6_09_strands_mcp.py
  └─ MCPClient + FastMCP 서버 연동
  └─ with MCPClient(...) as client: 블록 안에서만 Agent 호출 가능

P6_10_strands_react.py            ← 핵심
  └─ ReAct 패턴: system_prompt에 Thought/Action/Observation 단계 명시
  └─ P6_10_strands_react_rewoo_streamlit.py 원본

P6_11_strands_rewoo.py            ← 핵심
  └─ ReWOO 패턴: Planner(Agent) → Worker(직접 도구 호출) → Solver(Agent)
  └─ 세 개의 별도 Agent가 역할 분리

P6_10_strands_react_rewoo_streamlit.py  ← 시각화 추가
  └─ ReAct vs ReWOO 동일 질문으로 탭 비교
  └─ ReWOO: Planner 계획표 / Worker 결과 / Solver 답변 3단계 시각화
```

---

## 코드에서 중요한 부분

### 1. Strands 기본 패턴
```python
from strands import Agent, tool
from strands.models import BedrockModel

model = BedrockModel(
    model_id="global.anthropic.claude-sonnet-4-6",
    boto_session=boto3.Session(region_name="us-east-1"),
    streaming=True,
)

@tool
def weather_forecast(city: str) -> str:
    """지정한 도시의 현재 날씨를 조회한다.
    Args:
        city: 날씨를 조회할 도시 이름 (영문)
    """
    ...

agent = Agent(model=model, tools=[weather_forecast], system_prompt="...")
agent("서울 날씨 알려줘")  # 자동으로 도구 호출 루프 처리
```

### 2. `@tool` 데코레이터 — docstring이 도구 설명이 됨
```python
@tool
def my_tool(param: str) -> str:
    """한 줄 설명 — 모델이 언제 이 도구를 쓸지 판단하는 근거.
    Args:
        param: 파라미터 설명 (타입힌트 → JSON Schema 자동 생성)
    """
```

### 3. 세션 저장/복원 패턴 (P6_05)
```python
# 저장
messages = agent.messages  # 대화 히스토리
json.dump(messages, f)

# 복원
loaded = json.load(f)
agent = Agent(model=model, messages=loaded)  # 이전 대화 이어서
```

### 4. AgentResult 메트릭 (P6_06)
```python
result = agent("질문")
usage  = result.metrics.accumulated_usage
# → {'inputTokens': N, 'outputTokens': N, 'totalTokens': N}
tools  = result.metrics.tool_metrics
# → {'calculator': ToolMetrics(call_count=1, ...)}
```

### 5. MCPClient — with 블록 필수 (P6_09)
```python
with MCPClient(make_transport) as mcp_client:
    tools = mcp_client.list_tools_sync()
    agent = Agent(model=model, tools=tools)
    agent("...")  # ← 반드시 with 블록 안에서 호출
# with 블록 밖에서 호출하면 MCP 서버 연결 끊김
```

### 6. ReWOO Worker — 도구 직접 호출 (P6_11)
```python
# agent.tool.xxx() 패턴으로 LLM 판단 없이 도구 직접 실행
raw = worker_agent.tool.weather_forecast(city="Seoul")
result_text = raw["content"][0]["text"]
```

---

## AWS만의 장점

| 장점 | 설명 |
|------|------|
| **Bedrock 완전 통합** | `BedrockModel`이 cross-region inference, IAM 인증을 자동 처리 |
| **strands_tools 내장** | calculator, http_request, file_read, current_time 즉시 사용 가능 |
| **MCP 표준 지원** | FastMCP 서버와 바로 연동 — 도구 생태계 확장 용이 |
| **callback_handler** | 모든 에이전트 이벤트를 훅으로 가로채기 가능 (로깅, UI 업데이트) |
| **오픈소스** | GitHub에서 소스 확인 및 기여 가능 (`strands-agents/strands`) |
| **Bedrock Knowledge Base 통합** | KnowledgeBaseTool로 RAG를 도구처럼 사용 가능 |

---

## P5 vs P6 핵심 차이

| | P5 (수동 Tool Use) | P6 (Strands) |
|---|---|---|
| 도구 루프 | 직접 while 루프 작성 | Agent 내부 자동 처리 |
| 도구 정의 | JSON Schema 직접 작성 | `@tool` 데코레이터 자동 생성 |
| 세션 관리 | 직접 messages 리스트 관리 | `agent.messages` + JSON 저장 |
| 멀티에이전트 | 직접 구조 설계 | Planner/Worker/Solver 분리 패턴 |

---

## 실행 순서

```bash
python3 P6_01_strands_setup.py          # 환경 확인
python3 P6_02_strands_agent.py          # 기본 Agent
python3 P6_05_strands_session.py        # 세션 저장/복원
python3 P6_08_strands_custom_tool.py    # 커스텀 @tool
python3 P6_09_strands_mcp.py            # MCP 연동
python3 P6_10_strands_react.py          # ReAct 패턴
python3 P6_11_strands_rewoo.py          # ReWOO 패턴

# Streamlit 시각화
streamlit run P6_10_strands_react_rewoo_streamlit.py \
  --server.port 8510 --server.headless true
```

---

## ReAct vs ReWOO 선택 기준

| 상황 | 권장 패턴 |
|------|----------|
| 결과를 봐야 다음 단계를 알 수 있는 탐색 작업 | ReAct |
| 단계가 미리 정해진 구조화된 반복 작업 | ReWOO |
| 여러 독립 도구를 병렬 실행해야 할 때 | ReWOO (Worker 병렬화 가능) |
| 중간에 계획을 바꿔야 할 수 있는 경우 | ReAct |
