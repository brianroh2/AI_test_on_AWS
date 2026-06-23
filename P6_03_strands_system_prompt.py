"""
P6_03_strands_system_prompt.py
────────────────────────────────────────────────────────────────────
Strands 챕터 03 — System Prompt 활용

03-1. system_prompt 지정 Agent
03-2. 역할극: 바리스타 Agent (input() 대화)

실행:
  python3 P6_03_strands_system_prompt.py
────────────────────────────────────────────────────────────────────
"""

import boto3
from strands import Agent
from strands.models import BedrockModel

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

session = boto3.Session(region_name=REGION)

streaming_model = BedrockModel(
    model_id=MODEL_ID,
    boto_session=session,
    streaming=True,
)

print("=" * 60)
print("  Part 6 — System Prompt 활용")
print("=" * 60)

# ── 03-1. system_prompt 지정 Agent ───────────────────────────────
print("\n[03-1] system_prompt로 역할 부여 (AWS 전문가)")

agent_expert = Agent(
    model=streaming_model,
    system_prompt="""
    당신은 AWS 클라우드 전문가입니다.
    - 모든 답변은 AWS 서비스 관점에서 설명합니다.
    - 핵심만 간결하게 답변합니다.
    - 관련 AWS 서비스명을 구체적으로 언급합니다.
    - 비용 효율적인 아키텍처를 항상 고려합니다.
    """,
)

agent_expert("AWS Lambda와 VPC 연결 시 RDS(MySQL) 접근 방법은?")

# ── 03-2. 역할극: 바리스타 Agent ─────────────────────────────────
print("\n\n[03-2] 역할극 — 바리스타 Agent")

agent_barista = Agent(
    model=streaming_model,
    system_prompt="""
    당신은 친근한 카페 바리스타입니다.
    역할:
    1. 음료 추천은 3~4가지 옵션을 제시합니다.
    2. 고객의 취향을 물어봅니다.
    3. 음료 설명은 맛있게 표현합니다.
    4. 항상 따뜻하고 친절한 말투를 사용합니다.
    메뉴:
    - 아메리카노: 에스프레소 / 다크로스팅 / 깔끔한 쓴맛
    - 카페라떼: 에스프레소 + 우유 / 부드러운 맛 / 달지 않음
    - 카푸치노: 에스프레소 + 거품우유 / 풍부한 거품 / 균형잡힌 맛
    - 콜드브루: 저온추출 / 은은한 단맛 / 여름 추천
    """,
)

print(f"  바리스타 Agent 준비 완료. (입력() 대신 자동 질문 실행)")
print(f"  ── 주의: input()는 자동화 환경에서 대신 고정 질문 사용 ──")
print()

questions = [
    "안녕하세요, 오늘 뭐 마실까요?",
    "달지 않고 진한 걸로 추천해줘",
]

for q in questions:
    print(f"\n[고객] {q}")
    print("-" * 40)
    agent_barista(q)
    print()

print(f"""
  ─────────────────────────────────────────────
  system_prompt 활용 팁:
    • Agent 생성 시 system_prompt= 로 역할 지정
    • Agent는 system_prompt에 따라 답변 스타일 결정
    • system_prompt가 없으면 기본 모델 동작

  ⚠️  주의:
    input() 사용 시 자동화 환경에서 블로킹됨
    → Streamlit 챗봇 등으로 대체 권장
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P6_03 완료 → P6_04 로 진행하세요")
print("=" * 60)
