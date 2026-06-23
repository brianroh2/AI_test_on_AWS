"""
P6_05_strands_session.py
────────────────────────────────────────────────────────────────────
Strands 챕터 05 — Session (대화 영속성)

05-1. 첫 번째 Agent 실행 + sessions/ 에 JSON 저장
05-2. 같은 session_id로 messages 로드 → Agent 재시작 → 대화 복원 확인

실행:
  python3 P6_05_strands_session.py
────────────────────────────────────────────────────────────────────
"""

import json
import os
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
print("  Part 6 — Session (대화 영속성)")
print("=" * 60)

# ── 세션 유틸리티 함수 ────────────────────────────────────────────

def save_session(session_id: str, messages: list, storage_dir: str = "./sessions") -> str:
    """Agent.messages 를 JSON 파일로 저장한다."""
    os.makedirs(storage_dir, exist_ok=True)
    path = os.path.join(storage_dir, f"{session_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    return path


def load_session(session_id: str, storage_dir: str = "./sessions") -> list:
    """JSON 파일에서 messages 를 로드한다. 파일이 없으면 [] 반환."""
    path = os.path.join(storage_dir, f"{session_id}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ── 05-1. 첫 번째 Agent 실행 + JSON 저장 ─────────────────────────
print("\n[05-1] 첫 번째 Agent 실행 — messages 를 JSON 으로 저장")

SESSION_ID  = "ramen-master-001"
SESSION_DIR = "./sessions"

agent_persist = Agent(
    model=conversation_model,
    system_prompt="친근한 라면 전문가입니다. 사용자의 이름과 취향을 기억합니다.",
)

agent_persist("내 이름은 박민수야. 나는 매운 라면을 좋아해. 내 최애 라면 3가지를 추천해줘.")

# 대화 기록 저장
saved_path = save_session(SESSION_ID, agent_persist.messages, SESSION_DIR)
print(f"\n  ✅ 세션 저장 완료: {saved_path}")
print(f"  저장된 메시지 수: {len(agent_persist.messages)}개")

# ── 05-2. Agent 재시작 — session_id 로 대화 복원 ─────────────────
print("\n\n[05-2] Agent 재시작 — session_id 로 대화 복원")

loaded_messages = load_session(SESSION_ID, SESSION_DIR)
print(f"  로드된 메시지 수: {len(loaded_messages)}개")

agent_restored = Agent(
    model=conversation_model,
    messages=loaded_messages,
    system_prompt="친근한 라면 전문가입니다. 사용자의 이름과 취향을 기억합니다.",
)

agent_restored("내가 좋아한다고 말한 라면 종류가 뭐였지?")

# 복원 후 추가 대화도 저장
save_session(SESSION_ID, agent_restored.messages, SESSION_DIR)
print(f"\n  ✅ 복원 후 추가 대화까지 저장 완료")

print(f"""
  ─────────────────────────────────────────────
  Session 핵심:
    • agent.messages → 메모리 내 대화 (재시작 시 사라짐)
    • save_session()  → JSON 파일로 messages 직렬화
    • load_session()  → JSON 파일에서 messages 복원
    • Agent(messages=loaded) → 이전 대화 이어서 진행

  Session 파일 위치: {SESSION_DIR}/{SESSION_ID}.json

  strands 0.3.0 참고:
    • FileSessionManager 모듈 미제공
    • agent.messages 직접 JSON 저장/로드로 동일 효과
    • S3 저장도 동일 방식으로 확장 가능
      (boto3 s3.put_object / s3.get_object 사용)
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P6_05 완료 → P6_06 으로 진행하세요")
print("=" * 60)
