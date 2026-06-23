# Part 6 — Strands Agentic AI 콘솔 따라하기

AWS 브라우저(콘솔)에서 Strands Agent의 기반 서비스와 MCP 연동을 직접 확인하는 가이드입니다.  
Strands 자체는 Python 라이브러리이므로 코드 실습이 핵심이지만,  
콘솔에서 기반 서비스(Bedrock, CloudWatch)와 ReAct/ReWOO 동작 원리를 시각적으로 확인할 수 있습니다.

---

## Strands Agent 란?

AWS가 만든 오픈소스 AI 에이전트 프레임워크입니다.  
`@tool` 데코레이터 하나로 함수를 도구로 등록하고,  
Agent가 스스로 어떤 도구를 언제 쓸지 결정합니다.

```python
from strands import Agent, tool

@tool
def get_weather(city: str) -> str:
    """도시의 날씨를 반환합니다."""
    ...

agent = Agent(tools=[get_weather])
agent("서울 날씨 알려줘")  # Agent가 알아서 get_weather 호출
```

---

## 전체 흐름

```
1단계: Bedrock 콘솔에서 모델 확인 (Strands가 사용하는 모델)
2단계: Bedrock Playground에서 Agent 동작 체험
3단계: ReAct / ReWOO 패턴 비교 이해
4단계: MCP 구조 이해 (woodcutter 서버 예시)
5단계: Python 코드 실행 순서
```

---

## 1단계. Strands가 사용하는 모델 확인

### 1-1. 모델 접근 확인

> **⚠️ UI 변경 안내 (2025년 이후)**  
> 기존 **Model access** 메뉴는 **Model catalog** 으로 통합되었습니다.

1. AWS 콘솔 → **Amazon Bedrock** 클릭
2. 왼쪽 메뉴 → **Model catalog** 클릭
3. 화면 상단에 **Serverless** / **Bedrock Marketplace** 탭이 표시됨 → **Serverless** 선택
4. 아래쪽 **Model filter** 입력창에 모델명 입력하여 검색
5. 검색 결과에서 모델 클릭 → 상세 페이지에서 접근 상태 확인

| 모델 | Model filter 입력값 | 용도 |
|------|-------------------|------|
| **Claude Sonnet 4.6** | `Claude Sonnet 4` | Strands 기본 모델 |
| **Claude Haiku 4.5** | `Claude Haiku 4` | 빠른 응답 / P7_02 |

> 접근 권한이 없으면 상세 페이지에서 **Request access** 버튼 클릭 → 즉시 승인됩니다.

---

### 1-2. Cross-Region Inference 확인

Strands는 `global.` 접두사 모델 ID로 Cross-Region Inference를 사용합니다.

1. 왼쪽 메뉴 → **Cross-region inference** 클릭
2. **Inference profiles** 탭에서 `global.anthropic.claude-sonnet-4-6` 확인
3. Status: **Active** 여야 합니다.

---

## 2단계. Bedrock Playground에서 Agent 동작 체험

Strands Agent의 핵심인 도구 선택과 다단계 추론을 콘솔에서 미리 체험합니다.

### 2-1. Chat Playground 접속

> **⚠️ UI 변경 안내 (2025년 이후)**  
> 메뉴 구조 변경: `Playgrounds → Chat` → `테스트 → Playground`  
> 진입 후 모델 선택도 별도 화면 없이 채팅 화면 상단 드롭다운으로 즉시 선택합니다.

1. 왼쪽 메뉴 → **테스트** → **Playground** 클릭
2. 화면 상단 모델 드롭다운 → **Anthropic** → **Claude Sonnet 4.6** 선택

### 2-2. System Prompt 설정 (Strands 스타일)

오른쪽 패널의 **System prompt** 입력창에 아래 내용 입력:

```
당신은 날씨와 시간 정보를 제공하는 AI 비서입니다.
사용자의 질문에 맞는 도구를 선택하여 정확한 정보를 제공하세요.
```

> Strands의 `system_prompt` 파라미터가 이 역할을 합니다.

### 2-3. Tool 추가 (날씨 + 시간)

**Tool use** 섹션에서 **Add tool** 클릭하여 2개 추가:

**도구 1 — 날씨:**

| 항목 | 입력값 |
|------|--------|
| **Tool name** | `weather_forecast` |
| **Description** | `지정한 도시의 현재 날씨를 조회합니다. 도시명은 영문으로 입력합니다.` |

```json
{
  "type": "object",
  "properties": {
    "city": {
      "type": "string",
      "description": "도시명 (영문). 예: Seoul, Tokyo, New York"
    }
  },
  "required": ["city"]
}
```

**도구 2 — 계산기:**

| 항목 | 입력값 |
|------|--------|
| **Tool name** | `calculator` |
| **Description** | `수식을 계산합니다. 예: 1234 * 5678` |

```json
{
  "type": "object",
  "properties": {
    "expression": {
      "type": "string",
      "description": "계산할 수식. 예: 1234 * 5678"
    }
  },
  "required": ["expression"]
}
```

### 2-4. 복합 질문 테스트

```
서울 날씨를 알려주고, 기온이 25도라면 화씨로 환산하면 얼마야?
```

> **예상 동작:**  
> 1. `weather_forecast(city="Seoul")` 호출 요청  
> 2. `calculator(expression="25 * 9/5 + 32")` 호출 요청  
> 두 도구를 순서대로 사용하는 패턴이 보입니다.  
> (실제 결과는 Python 코드에서 API 연결 후 확인)

---

## 3단계. ReAct vs ReWOO 패턴 이해

콘솔에서 두 패턴의 차이를 실험해 볼 수 있습니다.

### 3-1. ReAct 패턴 체험

**System Prompt:**
```
당신은 ReAct 패턴으로 동작하는 AI입니다.
매 단계마다 Thought(생각) → Action(도구 호출) → Observation(결과 확인) 순서로 진행하세요.
각 단계를 명시적으로 표시해 주세요.
```

**질문 입력:**
```
서울과 도쿄의 날씨를 각각 조회하고 어느 도시가 더 더운지 비교해줘
```

> **ReAct 특징:** 한 번에 하나씩 도구를 호출하며 결과를 확인하고 다음 단계를 결정합니다.  
> 중간 Thought 과정이 보입니다.

---

### 3-2. ReWOO 패턴 체험

**System Prompt:**
```
당신은 ReWOO 패턴으로 동작하는 AI입니다.
먼저 전체 실행 계획을 한 번에 수립하고, 계획에 따라 도구를 순서대로 실행하세요.
계획 수립 단계에서는 도구를 호출하지 말고, 계획만 작성하세요.
```

**질문 입력:**
```
서울과 도쿄의 날씨를 각각 조회하고 어느 도시가 더 더운지 비교해줘
```

> **ReWOO 특징:** 실행 계획을 먼저 모두 수립한 후 순서대로 실행합니다.  
> 계획 단계에서는 도구 호출이 없습니다.

---

### 3-3. 두 패턴 비교

| 항목 | ReAct | ReWOO |
|------|-------|-------|
| 도구 호출 방식 | 한 번에 하나씩, 결과 보고 다음 결정 | 전체 계획 후 순서대로 실행 |
| LLM 호출 횟수 | 도구마다 1회 (많음) | Planner 1회 + Solver 1회 (적음) |
| 유연성 | 높음 (중간에 방향 변경 가능) | 낮음 (계획 수정 어려움) |
| 비용 | 상대적으로 높음 | 상대적으로 낮음 |
| 적합한 상황 | 불확실하고 복잡한 작업 | 명확하고 예측 가능한 작업 |

> Strands 코드에서: `P6_10_strands_react.py` (ReAct) vs `P6_11_strands_rewoo.py` (ReWOO)  
> 시각화: `streamlit run P6_10_strands_react_rewoo_streamlit.py --server.port 8510`

---

## 4단계. MCP(Model Context Protocol) 구조 이해

### 4-1. MCP란?

MCP는 AI 모델이 외부 도구 서버와 표준화된 방식으로 통신하는 프로토콜입니다.  
이 실습에서는 `woodcutter_mcp_server.py`라는 로컬 MCP 서버를 사용합니다.

```
[Strands Agent]
    ↕ MCP 프로토콜 (stdio)
[woodcutter_mcp_server.py]
    ↕ 도구 함수 실행
[실제 API / 파일 / DB 등]
```

### 4-2. woodcutter MCP 서버 도구 목록 확인

터미널에서 실행:
```bash
python3 P6_09_strands_mcp.py
```

출력에서 MCP 서버가 제공하는 도구 목록 확인:
- 서버가 제공하는 도구 이름과 설명이 출력됩니다.
- Strands Agent는 이 도구들을 자신의 도구처럼 사용합니다.

### 4-3. 콘솔에서 MCP 개념 확인

1. AWS 콘솔 → **Amazon Bedrock** 클릭
2. 왼쪽 메뉴 → **Agents** 클릭
3. **Create Agent** → Action groups 섹션 확인

> Amazon Bedrock Agents의 **Action Groups**가 MCP의 도구 서버와 유사한 개념입니다.  
> 다만 이 실습에서는 Bedrock Agents 대신 Strands + 로컬 MCP 서버 방식을 사용합니다.

---

## 5단계. Python 코드 실행 순서

```bash
# 환경 확인
python3 P6_01_strands_setup.py

# Agent 기본 동작
python3 P6_02_strands_agent.py        # Stream / Non-Stream 비교
python3 P6_03_strands_system_prompt.py # System Prompt 활용
python3 P6_04_strands_memory.py        # 대화 메모리
python3 P6_05_strands_session.py       # 세션 영속성

# 도구 사용
python3 P6_06_strands_stat.py          # 통계/토큰 확인
python3 P6_07_strands_tools.py         # 내장 도구 (calculator, current_time 등)
python3 P6_08_strands_custom_tool.py   # @tool 커스텀 도구

# MCP
python3 P6_09_strands_mcp.py           # MCP 서버 연결

# 에이전트 패턴
python3 P6_10_strands_react.py         # ReAct 패턴
python3 P6_11_strands_rewoo.py         # ReWOO 패턴

# 시각화 비교
streamlit run P6_10_strands_react_rewoo_streamlit.py \
  --server.port 8510 --server.headless true
```

---

## 핵심 주의사항 요약

```
□ Strands 모델 ID: global.anthropic.claude-sonnet-4-6 (global. 접두사 필수)
□ @tool 데코레이터: docstring에 Args 설명 필수 (없으면 모델이 인자 파악 못함)
□ callback_handler=None: 출력 억제 + 결과만 반환 받을 때 사용
□ BYPASS_TOOL_CONSENT=true: http_request 도구 동의 프롬프트 건너뛰기
□ MCP with 블록: with mcp_client: 블록 안에서만 도구 사용 가능
□ ReAct vs ReWOO: 불확실한 작업 → ReAct / 명확한 작업 → ReWOO
```

---

## 참고 — Strands 핵심 코드 패턴

### @tool 데코레이터 기본

```python
from strands import Agent, tool

@tool
def weather_forecast(city: str) -> str:
    """지정한 도시의 현재 날씨를 조회한다.

    Args:
        city: 날씨를 조회할 도시 이름 (영문). 예: Seoul, Tokyo
    """
    # 실제 구현
    return f"{city}: 맑음, 25°C"

agent = Agent(tools=[weather_forecast])
agent("서울 날씨 알려줘")
```

### MCP 클라이언트 연결

```python
from mcp import StdioServerParameters
from strands.tools.mcp import MCPClient

mcp_client = MCPClient(lambda: StdioServerParameters(
    command="python3",
    args=["woodcutter_mcp_server.py"]
))

with mcp_client:
    agent = Agent(tools=mcp_client.list_tools_sync())
    agent("도구를 사용해 작업을 수행해줘")
```
