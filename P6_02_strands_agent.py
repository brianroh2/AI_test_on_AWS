"""
P6_02_strands_agent.py
────────────────────────────────────────────────────────────────────
Strands 챕터 02 — Agent Stream / Non-Stream / 출력 캡처

02-1. Stream Agent (streaming=True)
02-2. Non-Stream Agent (streaming=False)
02-3. 출력 억제 (callback_handler=None)
02-4. 결과 캡처 (result 객체)

실행:
  python3 P6_02_strands_agent.py
────────────────────────────────────────────────────────────────────
"""

import boto3
from strands import Agent
from strands.models import BedrockModel

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

session = boto3.Session(region_name=REGION)

print("=" * 60)
print("  Part 6 — Agent Stream / Non-Stream / 출력 캡처")
print("=" * 60)

# ── 02-1. Stream Agent ───────────────────────────────────────────
print("\n[02-1] Stream Agent (streaming=True)")

streaming_model = BedrockModel(
    model_id=MODEL_ID,
    boto_session=session,
    streaming=True,   # Stream ON
)

stream_agent = Agent(model=streaming_model)

print("  Agent 호출 (스트리밍 출력):")
stream_agent("인공지능이란 무엇인지 두 줄로 설명해줘.")

# ── 02-2. Non-Stream Agent ───────────────────────────────────────
print("\n\n[02-2] Non-Stream Agent (streaming=False)")

non_streaming_model = BedrockModel(
    model_id=MODEL_ID,
    boto_session=session,
    streaming=False,  # Stream OFF
)

non_stream_agent = Agent(model=non_streaming_model)

print("  Agent 호출 (논스트리밍 출력):")
non_stream_agent("머신러닝을 한 문장으로 설명해줘.")

# ── 02-3. 출력 억제 (callback_handler=None) ──────────────────────
print("\n\n[02-3] 출력 억제 (callback_handler=None)")

print("  [ Agent 응답 출력 없음 ]")
silent_agent = Agent(
    model=non_streaming_model,
    callback_handler=None,   # 출력 억제
)
result = silent_agent("딥러닝을 한 문장으로 설명해줘.")
print("  [ Agent 응답 끝 ]")

# ── 02-4. 결과 캡처 ──────────────────────────────────────────────
print("\n[02-4] result 객체로 결과 캡처")

print("  [ Agent 응답 출력 없음 ]")
result = silent_agent("강화학습을 한 문장으로 설명해줘.")
print("  [ Agent 응답 끝 ]")
print(f"\n  캡처된 결과:")
print(f"  → {str(result)[:200]}")

print(f"""
  ─────────────────────────────────────────────
  streaming=True  : 토큰 단위로 실시간 출력
  streaming=False : 완성 후 한 번에 출력

  agent(...)  호출 시 결과가 자동 출력 (print 불필요)
  callback_handler=None → 출력 억제, result 캡처용

  ⚠️  주의:
    agent(...) 호출 결과 → print(result) 로 중복 출력됨
    출력 억제가 필요하면 callback_handler=None 사용
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P6_02 완료 → P6_03 으로 진행하세요")
print("=" * 60)
