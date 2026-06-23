"""
P6_04_strands_memory.py
────────────────────────────────────────────────────────────────────
Strands 챕터 04 — 대화 메모리 (Memory)

04-1. 기본 Agent 대화 메모리 (자동)
04-2. 연속 질문 (이전 내용 기억 확인)
04-3. 긴 대화 후 요약 요청
04-4. agent.messages 확인
04-5. user 메시지만 필터링
04-6. Agent 초기화 시 messages 주입

실행:
  python3 P6_04_strands_memory.py
────────────────────────────────────────────────────────────────────
"""

import boto3
from strands import Agent
from strands.models import BedrockModel

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

session = boto3.Session(region_name=REGION)

conversation_model = BedrockModel(
    model_id=MODEL_ID,
    boto_session=session,
    streaming=True,
)

print("=" * 60)
print("  Part 6 — 대화 메모리 (Memory)")
print("=" * 60)

# ── 04-1. 기본 Agent 대화 메모리 ─────────────────────────────────
print("\n[04-1] 기본 Agent — 자동 대화 메모리")

agent_memory = Agent(
    model=conversation_model,
    system_prompt="""
    친근한 대화 상대입니다.
    - 이전 대화 내용을 기억합니다.
    - 간결하고 자연스럽게 답변합니다.
    - 상대방의 이름을 기억하면 활용합니다.
    """,
)

agent_memory("내 이름은 김철수야. 만나서 반가워!")

# ── 04-2. 연속 질문 (이전 내용 기억) ─────────────────────────────
print("\n\n[04-2] 연속 질문 — 이전 내용 기억 확인")

agent_memory("내 이름이 뭐라고 했지?")

# ── 04-3. 긴 대화 후 요약 요청 ───────────────────────────────────
print("\n\n[04-3] 긴 대화 후 요약 요청")

agent_memory("나는 파이썬 개발자이고, AWS에 관심이 많아. 요즘 AI 공부 중이야.")

# ── 04-4. agent.messages 확인 ────────────────────────────────────
print("\n\n[04-4] agent.messages 확인")

print("  현재 대화 기록:")
for item in agent_memory.messages:
    role = item["role"]
    # content는 리스트 또는 문자열
    if isinstance(item["content"], list):
        for c in item["content"]:
            if isinstance(c, dict) and "text" in c:
                print(f"  [{role}] {c['text'][:60]}...")
    else:
        print(f"  [{role}] {str(item['content'])[:60]}...")
    print()

# ── 04-5. user 메시지만 필터링 ───────────────────────────────────
print("[04-5] user 메시지만 필터링")

print("  사용자 질문 목록:")
for item in agent_memory.messages:
    if item["role"] == "user":
        if isinstance(item["content"], list):
            for c in item["content"]:
                if isinstance(c, dict) and "text" in c:
                    print(f"  - {c['text'][:80]}")

# ── 04-6. Agent 초기화 시 messages 주입 ──────────────────────────
print("\n[04-6] Agent 초기화 시 messages 주입")

pre_conv_history = [
    {"role": "user",      "content": [{"text": "안녕, 나는 이영희야. 라면 소믈리에야!"}]},
    {"role": "assistant", "content": [{"text": "안녕하세요 이영희님! 라면 소믈리에라니 흥미롭네요!"}]},
]

agent_injected = Agent(
    model=conversation_model,
    messages=pre_conv_history,
    system_prompt="친근한 대화 상대입니다. 이전 대화 내용을 기억합니다.",
)

agent_injected("내 직업이 뭐라고 했지?")

print(f"""
  ─────────────────────────────────────────────
  Strands Agent 메모리 핵심:
    • Agent는 자동으로 agent.messages 관리
    • 매 호출 시 대화 히스토리 누적
    • agent.messages → role + content 구조
    • Agent(messages=...) → 이전 대화 주입 가능

  ⚠️  주의:
    • Agent.messages(목록) role/content 키 사용
    • Agent(messages=...) 초기화 시 메모리 유지 안됨
      → session_manager 사용 권장 (05 참고)
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P6_04 완료 → P6_05 로 진행하세요")
print("=" * 60)
