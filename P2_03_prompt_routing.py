"""
P2_03_prompt_routing.py
────────────────────────────────────────────────────────────────────
주제: Bedrock Intelligent Prompt Routing
      — 요청 복잡도에 따라 자동으로 모델 분기 (Nova Lite ↔ Nova Pro)

핵심 개념:
  - 단순 질문 → 저렴한 모델(Nova Lite) 자동 선택
  - 복잡 질문 → 고품질 모델(Nova Pro) 자동 선택
  - responseQualityDifference: 분기 민감도 (0~100, 5단위)
    ┌─ 0   → 항상 저렴한 모델 (비용 최우선)
    ├─ 50  → 균형 (품질 차이 50% 이상이면 비싼 모델 사용)
    └─ 100 → 항상 고품질 모델 (품질 최우선)

실습 순서:
  1. Router 생성 (Nova Lite + Nova Pro)
  2. 직접 지정 vs Router 자동 분기 비교
  3. responseQualityDifference 값별 라우팅 차이
  4. 리소스 정리

실행:
  python3 P2_03_prompt_routing.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import time

REGION     = "us-east-1"
MODEL_LITE = f"arn:aws:bedrock:{REGION}::foundation-model/amazon.nova-lite-v1:0"
MODEL_PRO  = f"arn:aws:bedrock:{REGION}::foundation-model/amazon.nova-pro-v1:0"

bedrock_ctl = boto3.client("bedrock",         region_name=REGION)
bedrock     = boto3.client("bedrock-runtime", region_name=REGION)

SEP = "─" * 60


# ═══════════════════════════════════════════════════════════════
# 공통 헬퍼
# ═══════════════════════════════════════════════════════════════
def call(model_id: str, question: str, max_tokens: int = 200) -> tuple[str, str]:
    """(응답 텍스트, 실제 사용 모델) 반환"""
    resp = bedrock.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": question}]}],
        inferenceConfig={"maxTokens": max_tokens},
    )
    text = resp["output"]["message"]["content"][0]["text"].strip()
    # Router 응답에는 trace에 실제 모델 ID가 담김
    trace = resp.get("trace", {})
    invoked = trace.get("promptRouter", {}).get("invokedModelId", model_id)
    # 짧게 표시
    if "nova-lite" in invoked:
        used = "Nova Lite (저렴)"
    elif "nova-pro" in invoked:
        used = "Nova Pro  (고품질)"
    else:
        used = invoked.split("/")[-1]
    return text, used


# ═══════════════════════════════════════════════════════════════
# STEP 1: Router 생성
# ═══════════════════════════════════════════════════════════════
def step1_create_router(quality_diff: int = 5) -> str:
    name = f"demo-nova-router-{int(time.time())}"
    router = bedrock_ctl.create_prompt_router(
        promptRouterName=name,
        models=[
            {"modelArn": MODEL_LITE},
            {"modelArn": MODEL_PRO},
        ],
        fallbackModel={"modelArn": MODEL_LITE},
        routingCriteria={"responseQualityDifference": quality_diff},
    )
    arn = router["promptRouterArn"]
    print(f"\n  ✅ Router 생성: {name}")
    print(f"     ARN: {arn}")
    print(f"     responseQualityDifference: {quality_diff}")
    return arn


# ═══════════════════════════════════════════════════════════════
# STEP 2: 직접 지정 vs Router 자동 분기 비교
# ═══════════════════════════════════════════════════════════════
def step2_direct_vs_router(router_arn: str):
    print(f"\n{SEP}")
    print("【STEP 2】 직접 지정 vs Router 자동 분기")
    print(SEP)

    questions = [
        ("단순", "1+1=?"),
        ("복잡", "양자컴퓨터가 현재 RSA 암호화를 위협하는 이유와 "
                 "이에 대한 포스트 퀀텀 암호화의 접근법을 수학적으로 설명하세요."),
    ]

    for label, q in questions:
        print(f"\n  ── [{label}] 질문 ──")
        print(f"  {q[:80]}{'...' if len(q) > 80 else ''}")

        # 직접 Nova Lite 지정
        ans_lite, _ = call(MODEL_LITE, q)
        # 직접 Nova Pro 지정
        ans_pro, _  = call(MODEL_PRO,  q)
        # Router (자동 분기)
        ans_rt,  used = call(router_arn, q)

        print(f"\n  Nova Lite 직접  : {ans_lite[:100]}...")
        print(f"  Nova Pro  직접  : {ans_pro[:100]}...")
        print(f"\n  Router 응답     : {ans_rt[:100]}...")
        print(f"  Router 선택한 모델: ★ {used}")


# ═══════════════════════════════════════════════════════════════
# STEP 3: responseQualityDifference 값별 비교
#         같은 복잡한 질문을 서로 다른 QD 설정 Router로 호출
# ═══════════════════════════════════════════════════════════════
def step3_quality_diff_comparison():
    print(f"\n{SEP}")
    print("【STEP 3】 responseQualityDifference 설정별 라우팅 비교")
    print(SEP)
    print("  같은 질문을 QD=0 / QD=50 / QD=100 Router로 각각 호출")
    print("  → 실제 어떤 모델이 선택되는지 확인\n")

    QUESTION = "미적분학의 기본 정리를 직관적으로 설명해줘."

    configs = [
        (0,   "비용 최우선 (항상 Lite)"),
        (50,  "균형 (품질 차이 50% 이상이면 Pro)"),
        (100, "품질 최우선 (항상 Pro)"),
    ]

    arns = []
    for qd, desc in configs:
        name = f"demo-qd{qd}-{int(time.time())}"
        router = bedrock_ctl.create_prompt_router(
            promptRouterName=name,
            models=[{"modelArn": MODEL_LITE}, {"modelArn": MODEL_PRO}],
            fallbackModel={"modelArn": MODEL_LITE},
            routingCriteria={"responseQualityDifference": qd},
        )
        arns.append((qd, desc, router["promptRouterArn"]))

    print(f"  질문: {QUESTION}\n")
    for qd, desc, arn in arns:
        ans, used = call(arn, QUESTION)
        print(f"  QD={qd:3d} ({desc})")
        print(f"         선택 모델: {used}")
        print(f"         응답: {ans[:120]}...\n")

    # 정리
    for _, _, arn in arns:
        bedrock_ctl.delete_prompt_router(promptRouterArn=arn)
    print("  QD 테스트용 Router 3개 삭제 완료")


# ═══════════════════════════════════════════════════════════════
# STEP 4: invokedModelId 활용 — 실제 비용 추적 패턴
# ═══════════════════════════════════════════════════════════════
def step4_cost_tracking(router_arn: str):
    print(f"\n{SEP}")
    print("【STEP 4】 invokedModelId 활용 — 비용 추적 패턴")
    print(SEP)

    questions = [
        "오늘 날씨?",
        "2+2=?",
        "블록체인과 분산 원장의 핵심 차이점을 합의 알고리즘 관점에서 설명하세요.",
        "파이썬 리스트 정렬 방법은?",
    ]

    cost_log = {"Nova Lite (저렴)": 0, "Nova Pro  (고품질)": 0}

    print(f"\n  {'질문':30s}  {'선택 모델':20s}")
    print(f"  {'─'*30}  {'─'*20}")
    for q in questions:
        _, used = call(router_arn, q, max_tokens=50)
        cost_log[used] = cost_log.get(used, 0) + 1
        print(f"  {q[:30]:30s}  {used}")

    print(f"\n  📊 모델 호출 횟수:")
    for model, cnt in cost_log.items():
        print(f"     {model}: {cnt}회")
    print(f"\n  💡 운영 tip: invokedModelId 로그를 CloudWatch에 저장하면")
    print(f"     모델별 비용을 실시간 추적할 수 있습니다.")


# ═══════════════════════════════════════════════════════════════
# STEP 5: 리소스 정리
# ═══════════════════════════════════════════════════════════════
def step5_cleanup(router_arn: str):
    print(f"\n{SEP}")
    print("【STEP 5】 리소스 정리")
    print(SEP)
    bedrock_ctl.delete_prompt_router(promptRouterArn=router_arn)
    print(f"\n  ✅ Router 삭제 완료")


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(" P2_03_prompt_routing.py")
    print(" Bedrock Intelligent Prompt Routing 실습")
    print("=" * 60)

    print(f"\n{SEP}")
    print("【STEP 1】 Router 생성 (QD=5, 기본값)")
    print(SEP)
    router_arn = step1_create_router(quality_diff=5)

    step2_direct_vs_router(router_arn)
    step3_quality_diff_comparison()
    step4_cost_tracking(router_arn)
    step5_cleanup(router_arn)

    print(f"\n{'=' * 60}")
    print("완료")
    print("=" * 60)
