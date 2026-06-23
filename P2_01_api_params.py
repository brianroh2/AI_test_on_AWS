"""
P2_01_api_params.py
────────────────────────────────────────────────────────────────────
주제: AWS Bedrock API 파라미터 구조 — 일반 Anthropic SDK vs Bedrock Converse

핵심 차이점 3가지를 동일 결과로 직접 비교:
  A) inferenceConfig 래퍼 (temperature / maxTokens / topP 전달 방식)
  B) MODEL_ID — cross-region inference profile 접두사 (us. / global.)
  C) additionalModelRequestFields — Extended Thinking(reasoning_config)

실행:
  python3 P2_01_api_params.py
────────────────────────────────────────────────────────────────────
"""

import boto3
from anthropic import AnthropicBedrock

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"   # ← global. 접두사 (전 세계 리전 분산)

bedrock  = boto3.client("bedrock-runtime", region_name=REGION)

SEP = "─" * 60


# ═══════════════════════════════════════════════════════════════
# 비교 A: inferenceConfig 래퍼
# ═══════════════════════════════════════════════════════════════
def compare_a_inference_config():
    print(f"\n{SEP}")
    print("【A】 inferenceConfig 래퍼 비교")
    print(SEP)

    QUESTION = "파이썬의 장점을 딱 한 문장으로."

    # ─── 방법 1: Anthropic SDK (직접 파라미터) ───────────────────
    client = AnthropicBedrock(aws_region=REGION)
    msg = client.messages.create(
        model=MODEL_ID,
        max_tokens=100,         # ← 최상위 직접 전달
        temperature=0.0,        # ← 최상위 직접 전달
        messages=[{"role": "user", "content": QUESTION}],
    )
    answer_sdk = msg.content[0].text.strip()

    # ─── 방법 2: Bedrock Converse (inferenceConfig 래퍼 필수) ─────
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": QUESTION}]}],
        inferenceConfig={           # ← 반드시 이 딕셔너리 안에 넣어야 함
            "maxTokens":  100,      #    (직접 최상위에 쓰면 TypeError)
            "temperature": 0.0,
        },
    )
    answer_boto = resp["output"]["message"]["content"][0]["text"].strip()

    print(f"\n  질문: {QUESTION}")
    print(f"\n  [Anthropic SDK]  max_tokens=100, temperature=0.0  (직접)")
    print(f"  응답: {answer_sdk}")
    print(f"\n  [Bedrock Converse] inferenceConfig={{maxTokens:100, temperature:0.0}}")
    print(f"  응답: {answer_boto}")
    print(f"\n  ✅ 같은 결과 — 파라미터 위치만 다름")


# ═══════════════════════════════════════════════════════════════
# 비교 B: MODEL_ID cross-region 접두사
# ═══════════════════════════════════════════════════════════════
def compare_b_model_id():
    print(f"\n{SEP}")
    print("【B】 MODEL_ID cross-region 접두사 비교")
    print(SEP)

    QUESTION = "AWS란? 한 줄로."

    # ─── 접두사 없음 (직접 모델 ID) ───────────────────────────────
    model_direct = "anthropic.claude-sonnet-4-6"   # 리전 내 직접 호출
    try:
        resp = bedrock.converse(
            modelId=model_direct,
            messages=[{"role": "user", "content": [{"text": QUESTION}]}],
            inferenceConfig={"maxTokens": 80},
        )
        ans_direct = resp["output"]["message"]["content"][0]["text"].strip()
        print(f"\n  모델ID: {model_direct}")
        print(f"  응답: {ans_direct}")
        print(f"  → 현재 환경에서 직접 ID도 허용됨")
    except Exception as e:
        print(f"\n  모델ID: {model_direct}  → 오류: {type(e).__name__}")

    # ─── us. 접두사 (Cross-region Inference Profile) ──────────────
    model_cross = "global.anthropic.claude-sonnet-4-6"
    resp = bedrock.converse(
        modelId=model_cross,
        messages=[{"role": "user", "content": [{"text": QUESTION}]}],
        inferenceConfig={"maxTokens": 80},
    )
    ans_cross = resp["output"]["message"]["content"][0]["text"].strip()
    print(f"\n  모델ID: {model_cross}  (global. 접두사)")
    print(f"  응답: {ans_cross}")

    print(f"\n  💡 접두사 역할:")
    print(f"     us.      → us-east-1 / us-west-2 중 가용한 리전 자동 분산")
    print(f"     global.  → 전 세계 리전 자동 분산")
    print(f"     없음     → 지정 리전 단일 호출 (트래픽 급증 시 ThrottlingException 위험)")


# ═══════════════════════════════════════════════════════════════
# 비교 C: additionalModelRequestFields — Extended Thinking
# ═══════════════════════════════════════════════════════════════
def compare_c_additional_fields():
    print(f"\n{SEP}")
    print("【C】 additionalModelRequestFields — Extended Thinking")
    print(SEP)

    QUESTION = "닭이 먼저일까 달걀이 먼저일까? 근거와 함께 결론 내려줘."

    # ─── 일반 호출 (thinking 없음) ────────────────────────────────
    resp_normal = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": QUESTION}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 1.0},
    )
    ans_normal = resp_normal["output"]["message"]["content"][0]["text"].strip()

    # ─── Extended Thinking 활성화 ─────────────────────────────────
    # additionalModelRequestFields: Bedrock 전용 확장 파라미터
    # reasoning_config는 inferenceConfig에 넣으면 오류 → 반드시 여기에
    try:
        resp_think = bedrock.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": QUESTION}]}],
            inferenceConfig={
                "maxTokens": 8000,  # thinking 사용 시 2000 이상 권장
                "temperature": 1.0, # thinking 모드에선 temperature=1 고정
            },
            additionalModelRequestFields={   # ← Bedrock 전용 확장 파라미터
                "thinking": {
                    "type": "enabled",       # "enabled": 항상 활성화
                    "budget_tokens": 2000,   # 최대 내부 사고 토큰
                }
            },
        )
        thinking_text = ""
        answer_text   = ""
        for block in resp_think["output"]["message"]["content"]:
            if block.get("reasoningContent"):
                thinking_text = block["reasoningContent"].get("reasoningText", {}).get("text", "")
            elif block.get("text"):
                answer_text = block["text"]

        print(f"\n  질문: {QUESTION}")
        print(f"\n  ── 일반 응답 (thinking 없음) ──")
        print(f"  {ans_normal[:200]}")
        print(f"\n  ── Extended Thinking 활성화 ──")
        if thinking_text:
            print(f"  [내부 사고 ({len(thinking_text)}자)]")
            print(f"  {thinking_text[:300]}...")
        print(f"\n  [최종 응답]")
        print(f"  {answer_text[:300]}")
        print(f"\n  💡 additionalModelRequestFields 역할:")
        print(f"     inferenceConfig에 없는 모델별 확장 기능을 전달하는 전용 필드")
        print(f"     reasoning_config 외에도 추후 AWS가 기능 추가 시 이 필드로 전달")

    except Exception as e:
        print(f"\n  Extended Thinking 오류 ({type(e).__name__}): {e}")
        print(f"  → ValidationException이면 해당 모델 미지원")


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(" P2_01_api_params.py")
    print(" AWS Bedrock API 파라미터 구조 비교")
    print("=" * 60)

    compare_a_inference_config()
    compare_b_model_id()
    compare_c_additional_fields()

    print(f"\n{SEP}")
    print("완료")
    print(SEP)
