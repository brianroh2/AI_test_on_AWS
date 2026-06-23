"""
P6_07_strands_tools.py
────────────────────────────────────────────────────────────────────
Strands 챕터 07 — 내장 도구 (Built-in Tools)

07-1. 내장 도구 목록 확인 (calculator, http_request, file_read, file_write, current_time)
07-2. calculator — 수식 계산
07-3. current_time — 현재 시간
07-4. file_write + file_read — 파일 쓰기/읽기
07-5. http_request — HTTP GET 요청 (BYPASS_TOOL_CONSENT)
07-6. agent.tool.xxx — 도구 직접 호출

실행:
  python3 P6_07_strands_tools.py
────────────────────────────────────────────────────────────────────
"""

import os
import boto3
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator, http_request, file_read, file_write, current_time

# http_request 동의 프롬프트 건너뛰기
os.environ["BYPASS_TOOL_CONSENT"] = "true"

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

session = boto3.Session(region_name=REGION)

model = BedrockModel(
    model_id=MODEL_ID,
    boto_session=session,
    streaming=True,
)

model_ns = BedrockModel(
    model_id=MODEL_ID,
    boto_session=session,
    streaming=False,
)

print("=" * 60)
print("  Part 6 — 내장 도구 (Built-in Tools)")
print("=" * 60)

# ── 07-1. 내장 도구 목록 ─────────────────────────────────────────
print("\n[07-1] 내장 도구 목록")

BUILTIN_TOOLS = {
    "calculator" : calculator,
    "http_request": http_request,
    "file_read"  : file_read,
    "file_write" : file_write,
    "current_time": current_time,
}

for name, tool in BUILTIN_TOOLS.items():
    pkg = getattr(tool, "__package__", "strands_tools")
    print(f"  • {name:15s} ← {pkg}.{name}")

# ── 07-2. calculator ─────────────────────────────────────────────
print("\n[07-2] calculator — 수식 계산")

agent_calc = Agent(model=model, tools=[calculator])
agent_calc("(1024 ** 2) + (768 ** 2) 를 계산하고 결과를 알려줘")

# ── 07-3. current_time ───────────────────────────────────────────
print("\n\n[07-3] current_time — 현재 시간 조회")

agent_time = Agent(model=model, tools=[current_time])
agent_time("서울, 뉴욕, 런던의 현재 시간을 알려줘")

# ── 07-4. file_write + file_read ─────────────────────────────────
print("\n\n[07-4] file_write + file_read — 파일 쓰기/읽기")

agent_file = Agent(model=model, tools=[file_write, file_read])
agent_file(
    "./tmp_memo.txt 파일에 '안녕하세요! Strands file_write 테스트입니다.' 라고 저장하고, "
    "다시 읽어서 내용을 확인해줘"
)

# ── 07-5. http_request ───────────────────────────────────────────
print("\n\n[07-5] http_request — HTTP GET 요청")

agent_http = Agent(model=model, tools=[http_request])
agent_http("https://httpbin.org/get 에 GET 요청을 보내고 응답의 url 필드 값을 알려줘")

# ── 07-6. agent.tool.xxx — 직접 호출 ─────────────────────────────
print("\n\n[07-6] agent.tool.xxx — 도구 직접 호출")

agent_direct = Agent(
    model=model_ns,
    tools=[calculator, current_time],
    callback_handler=None,
)

# calculator 직접 호출
calc_result = agent_direct.tool.calculator(expression="2 ** 10", mode="evaluate")
print(f"  calculator(2**10)  → {calc_result['content'][0]['text']}")

# current_time 직접 호출
time_result = agent_direct.tool.current_time(timezone="Asia/Seoul")
print(f"  current_time(Seoul) → {time_result['content'][0]['text']}")

print(f"""
  ─────────────────────────────────────────────
  내장 도구 핵심:
    • from strands_tools import calculator, http_request, ...
    • Agent(tools=[calculator, ...]) 로 도구 등록
    • Agent 가 자동으로 도구 선택 및 호출
    • agent.tool.calculator(...) → 도구 직접 호출 가능

  BYPASS_TOOL_CONSENT:
    • os.environ["BYPASS_TOOL_CONSENT"] = "true"
    • http_request 실행 전 동의 프롬프트 생략

  ⚠️  주의:
    • file_write 경로는 상대경로 / 절대경로 모두 가능
    • http_request 는 외부 URL 호출 → 네트워크 필요
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P6_07 완료 → P6_08 로 진행하세요")
print("=" * 60)
