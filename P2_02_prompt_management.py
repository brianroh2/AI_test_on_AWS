"""
P2_02_prompt_management.py
────────────────────────────────────────────────────────────────────
주제: Bedrock Prompt Management — 코드 외부 프롬프트 버전 관리

일반 방식(코드에 프롬프트 하드코딩)과
Bedrock Prompt Management(ARN 기반 호출) 를 직접 비교합니다.

실습 순서:
  1. 일반 방식  — 프롬프트를 코드 문자열로 전달
  2. PM 방식    — Bedrock에 프롬프트 저장 → ARN으로 호출
  3. 업데이트   — 프롬프트 v2 생성 → ARN만 바꿔서 호출 (코드 변경 없음)
  4. 정리       — 생성한 리소스 삭제

실행:
  python3 P2_02_prompt_management.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import time

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
agent   = boto3.client("bedrock-agent",   region_name=REGION)

# 실행마다 고유 이름으로 충돌 방지
PROMPT_NAME = f"demo-plan-advisor-{int(time.time())}"

SEP = "─" * 60


# ═══════════════════════════════════════════════════════════════
# 공통 헬퍼
# ═══════════════════════════════════════════════════════════════
def converse_text(model_id_or_arn: str, user_text: str,
                  prompt_vars: dict | None = None) -> str:
    kwargs: dict = {"modelId": model_id_or_arn}
    if prompt_vars:
        # Prompt Management ARN 호출 시 inferenceConfig 전달 불가 (현재 미지원)
        # → 프롬프트 variant에 설정된 모델 설정이 그대로 적용됨
        kwargs["promptVariables"] = prompt_vars
    else:
        kwargs["inferenceConfig"] = {"maxTokens": 200}
        kwargs["messages"] = [
            {"role": "user", "content": [{"text": user_text}]}
        ]
    resp = bedrock.converse(**kwargs)
    return resp["output"]["message"]["content"][0]["text"].strip()


# ═══════════════════════════════════════════════════════════════
# STEP 1: 일반 방식 — 코드에 프롬프트 하드코딩
# ═══════════════════════════════════════════════════════════════
def step1_hardcoded(usage: str, count: str) -> str:
    print(f"\n{SEP}")
    print("【STEP 1】 일반 방식 — 프롬프트 코드 내 하드코딩")
    print(SEP)

    # ↓ 이 문자열이 바뀌면 코드를 수정·배포해야 함
    PROMPT_TEMPLATE = (
        f"당신은 통신사 요금제 전문 상담사입니다.\n"
        f"'{usage}' 사용자에게 적합한 요금제를 {count}개 추천해주세요.\n"
        f"각 요금제에 간단한 이유를 포함하세요."
    )

    answer = converse_text(MODEL_ID, PROMPT_TEMPLATE)
    print(f"\n  사용자: usage={usage}, count={count}")
    print(f"  프롬프트: (코드 내 f-string 직접 작성)")
    print(f"  응답:\n{answer}")
    return answer


# ═══════════════════════════════════════════════════════════════
# STEP 2: Prompt Management — Bedrock에 프롬프트 저장
# ═══════════════════════════════════════════════════════════════
def step2_create_prompt() -> tuple[str, str]:
    """프롬프트 생성 → 버전 고정 → ARN 반환"""
    print(f"\n{SEP}")
    print("【STEP 2】 Prompt Management — 프롬프트 생성 & 버전 고정")
    print(SEP)

    # ── 프롬프트 생성 ({{변수}} 템플릿) ─────────────────────────
    resp = agent.create_prompt(
        name=PROMPT_NAME,
        description="요금제 추천 상담사 — demo용",
        variants=[{
            "name": "v1",
            "modelId": MODEL_ID,
            "templateType": "TEXT",
            "templateConfiguration": {
                "text": {
                    # {{usage}}, {{count}} 는 Bedrock 변수 문법
                    "text": (
                        "당신은 통신사 요금제 전문 상담사입니다.\n"
                        "'{{usage}}' 사용자에게 적합한 요금제를 {{count}}개 추천해주세요.\n"
                        "각 요금제에 간단한 이유를 포함하세요."
                    ),
                    "inputVariables": [
                        {"name": "usage"},
                        {"name": "count"},
                    ],
                }
            },
        }],
    )
    prompt_id = resp["id"]
    print(f"\n  ✅ 프롬프트 생성 완료")
    print(f"     ID:   {prompt_id}")

    # ── 버전 고정 (배포용 ARN 발급) ──────────────────────────────
    ver = agent.create_prompt_version(promptIdentifier=prompt_id)
    prompt_arn = ver["arn"]
    print(f"     ARN:  {prompt_arn}")
    print(f"     → 이 ARN을 modelId 대신 사용하면 Bedrock이 프롬프트를 주입함")

    return prompt_id, prompt_arn


# ═══════════════════════════════════════════════════════════════
# STEP 3: ARN으로 호출 — 코드에 프롬프트 문자열 없음
# ═══════════════════════════════════════════════════════════════
def step3_call_with_arn(prompt_arn: str, usage: str, count: str) -> str:
    print(f"\n{SEP}")
    print("【STEP 3】 ARN 기반 호출 — promptVariables만 전달")
    print(SEP)

    answer = converse_text(
        model_id_or_arn=prompt_arn,      # ← 모델ID 대신 ARN
        user_text="",                     # messages 불필요 (프롬프트가 Bedrock에서 주입됨)
        prompt_vars={
            "usage": {"text": usage},    # ← 변수값만 전달
            "count": {"text": count},
        },
    )

    print(f"\n  ARN: {prompt_arn}")
    print(f"  변수: usage={usage}, count={count}")
    print(f"  응답:\n{answer}")
    print(f"\n  💡 코드 어디에도 프롬프트 문자열이 없음!")
    print(f"     프롬프트를 수정하려면 Bedrock 콘솔 or agent.create_prompt() 만 호출하면 됨")
    return answer


# ═══════════════════════════════════════════════════════════════
# STEP 4: 프롬프트 업데이트 시뮬레이션
#         v1 → v2 (톤 변경) — 호출 코드는 ARN 교체만
# ═══════════════════════════════════════════════════════════════
def step4_update_prompt(prompt_id: str, usage: str, count: str) -> str:
    print(f"\n{SEP}")
    print("【STEP 4】 프롬프트 업데이트 — v2 생성 (코드 변경 없음)")
    print(SEP)

    # ── 새 버전 내용으로 프롬프트 수정 ───────────────────────────
    agent.update_prompt(
        promptIdentifier=prompt_id,
        name=PROMPT_NAME,
        variants=[{
            "name": "v2",
            "modelId": MODEL_ID,
            "templateType": "TEXT",
            "templateConfiguration": {
                "text": {
                    "text": (
                        "당신은 친근한 통신사 AI 상담봇 '모비'입니다. 😊\n"
                        "이모지를 적극 활용해 밝고 간결하게 답변하세요.\n"
                        "'{{usage}}' 고객님께 딱 맞는 요금제 {{count}}가지를 추천드립니다!"
                    ),
                    "inputVariables": [
                        {"name": "usage"},
                        {"name": "count"},
                    ],
                }
            },
        }],
    )

    # ── 새 버전 고정 ─────────────────────────────────────────────
    ver2 = agent.create_prompt_version(promptIdentifier=prompt_id)
    arn_v2 = ver2["arn"]
    print(f"\n  v2 ARN: {arn_v2}")
    print(f"  → 호출 측에서 ARN만 v2로 교체하면 새 프롬프트 즉시 적용")

    answer = converse_text(
        model_id_or_arn=arn_v2,
        user_text="",
        prompt_vars={
            "usage": {"text": usage},
            "count": {"text": count},
        },
    )
    print(f"\n  [v2 응답 — 톤 변경됨]\n{answer}")
    return answer


# ═══════════════════════════════════════════════════════════════
# STEP 5: 정리 (생성 리소스 삭제)
# ═══════════════════════════════════════════════════════════════
def step5_cleanup(prompt_id: str):
    print(f"\n{SEP}")
    print("【STEP 5】 리소스 정리")
    print(SEP)
    agent.delete_prompt(promptIdentifier=prompt_id)
    print(f"\n  ✅ 프롬프트 {prompt_id} 삭제 완료")
    print(f"     (모든 버전 자동 삭제)")


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(" P2_02_prompt_management.py")
    print(" Bedrock Prompt Management 비교 실습")
    print("=" * 60)

    USAGE = "영상 스트리밍"
    COUNT = "2"

    # STEP 1: 일반 하드코딩 방식
    step1_hardcoded(USAGE, COUNT)

    # STEP 2~4: Prompt Management 방식
    prompt_id, prompt_arn = step2_create_prompt()
    step3_call_with_arn(prompt_arn, USAGE, COUNT)
    step4_update_prompt(prompt_id, USAGE, COUNT)

    # STEP 5: 정리
    step5_cleanup(prompt_id)

    print(f"\n{'=' * 60}")
    print("완료")
    print("=" * 60)
