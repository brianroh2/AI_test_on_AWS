"""
P2_05_prompt_optimization.py
────────────────────────────────────────────────────────────────────
주제: Bedrock Prompt Optimization
      — AI가 자동으로 프롬프트 품질을 개선

두 가지 기능:
  A) optimize_prompt API — 단일 프롬프트 즉시 최적화
  B) 최적화 전/후 실제 응답 품질 비교

※ Advanced Prompt Optimization (AdvPO) 은 Bedrock UI에서 실행하는
  배치 작업이므로 이 파일에서는 JSONL 데이터 생성까지만 다룹니다.

실행:
  python3 P2_05_prompt_optimization.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import json
import re

REGION          = "us-east-1"
MODEL_ID        = "global.anthropic.claude-sonnet-4-6"
TARGET_MODEL_ID = "anthropic.claude-sonnet-4-6"   # optimize_prompt는 cross-region prefix 없이

bedrock   = boto3.client("bedrock-runtime",      region_name=REGION)
optimizer = boto3.client("bedrock-agent-runtime", region_name=REGION)

SEP = "─" * 60


# ═══════════════════════════════════════════════════════════════
# 유틸: \uXXXX 이스케이프 디코딩 (API 응답 정규화)
# ═══════════════════════════════════════════════════════════════
def _decode(text: str) -> str:
    r"""optimize_prompt API가 반환하는 \uXXXX 이스케이프를 실제 유니코드로 변환.
    API 버그로 첫 번째 이스케이프의 역슬래시가 누락되는 경우를 함께 처리.
    """
    s = text.strip()
    if s.startswith('"') and s.endswith('"'):
        inner = s[1:-1]
        # 역슬래시 없이 시작하는 uXXXX 패턴도 \uXXXX 로 보정
        inner_fixed = re.sub(r'(?<!\\)u([0-9a-fA-F]{4})', r'\\u\1', inner)
        try:
            return json.loads('"' + inner_fixed + '"')
        except Exception:
            pass
    # fallback: \uXXXX 직접 치환
    return re.sub(r'\\u([0-9a-fA-F]{4})',
                  lambda m: chr(int(m.group(1), 16)), s).strip('"')


# ═══════════════════════════════════════════════════════════════
# 핵심 함수: optimize_prompt 호출
# ═══════════════════════════════════════════════════════════════
def optimize(prompt_text: str) -> str:
    resp = optimizer.optimize_prompt(
        input={"textPrompt": {"text": prompt_text}},
        targetModelId=TARGET_MODEL_ID,
    )
    for event in resp["optimizedPrompt"]:
        if "optimizedPromptEvent" in event:
            raw = event["optimizedPromptEvent"]["optimizedPrompt"]["textPrompt"]["text"]
            return _decode(raw)
    return prompt_text   # fallback


def ask(prompt: str, max_tokens: int = 300) -> str:
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": max_tokens},
    )
    return resp["output"]["message"]["content"][0]["text"].strip()


# ═══════════════════════════════════════════════════════════════
# STEP 1: 단순 프롬프트 최적화 — 요청이 모호할수록 차이가 큼
# ═══════════════════════════════════════════════════════════════
def step1_single_optimize():
    print(f"\n{SEP}")
    print("【STEP 1】 단일 프롬프트 최적화 비교")
    print(SEP)

    test_cases = [
        "요금제 추천해줘",
        "이메일 써줘",
        "코드 고쳐줘",
    ]

    for original in test_cases:
        optimized = optimize(original)
        print(f"\n  원본:     {original}")
        print(f"  최적화:   {optimized[:300]}")
        print(f"  {'─'*50}")


# ═══════════════════════════════════════════════════════════════
# STEP 2: 최적화 전/후 실제 응답 품질 비교
# ═══════════════════════════════════════════════════════════════
def step2_quality_comparison():
    print(f"\n{SEP}")
    print("【STEP 2】 최적화 전/후 응답 품질 직접 비교")
    print(SEP)

    cases = [
        {
            "label": "요금제 추천",
            "original": "요금제 추천해줘",
        },
        {
            "label": "회의록 작성",
            "original": "회의록 써줘",
        },
    ]

    for case in cases:
        original  = case["original"]
        optimized = optimize(original)

        print(f"\n  ══ {case['label']} ══")
        print(f"\n  [원본 프롬프트] → {original}")
        ans_before = ask(original)
        print(f"  응답:\n{ans_before[:400]}\n")

        print(f"  [최적화 프롬프트] → {optimized[:200]}...")
        ans_after = ask(optimized)
        print(f"  응답:\n{ans_after[:400]}")

        print(f"\n  📌 차이점:")
        print(f"     원본 응답 길이: {len(ans_before)}자")
        print(f"     최적화 응답 길이: {len(ans_after)}자")
        print(f"     {'─'*50}")


# ═══════════════════════════════════════════════════════════════
# STEP 3: optimize_prompt analyzePromptEvent 로그 확인
# ═══════════════════════════════════════════════════════════════
def step3_analyze_events():
    print(f"\n{SEP}")
    print("【STEP 3】 analyzePromptEvent — 최적화 과정 단계 로그")
    print(SEP)
    print("  optimize_prompt는 스트리밍으로 두 종류의 이벤트를 반환합니다:")
    print("  - analyzePromptEvent  : 분석 진행 상황 메시지")
    print("  - optimizedPromptEvent: 최종 최적화 결과\n")

    original = "SQL 쿼리 최적화해줘"
    print(f"  원본: {original}\n")

    resp = optimizer.optimize_prompt(
        input={"textPrompt": {"text": original}},
        targetModelId=TARGET_MODEL_ID,
    )

    for event in resp["optimizedPrompt"]:
        if "analyzePromptEvent" in event:
            msg = event["analyzePromptEvent"].get("message", "")
            print(f"  [분석] {msg}")
        elif "optimizedPromptEvent" in event:
            raw = event["optimizedPromptEvent"]["optimizedPrompt"]["textPrompt"]["text"]
            result = _decode(raw)
            print(f"\n  [결과] {result[:400]}")


# ═══════════════════════════════════════════════════════════════
# STEP 4: Advanced Prompt Optimization용 JSONL 생성
#         (실제 AdvPO 실행은 Bedrock 콘솔 UI에서 수행)
# ═══════════════════════════════════════════════════════════════
def step4_advpo_jsonl():
    print(f"\n{SEP}")
    print("【STEP 4】 Advanced Prompt Optimization — JSONL 데이터 생성")
    print(SEP)
    print("  AdvPO는 Bedrock 콘솔 UI에서 실행하는 배치 작업입니다.")
    print("  이 코드는 입력 데이터(JSONL)를 생성하는 부분만 시연합니다.\n")

    PLAN_INFO = (
        "요금제A: 월 3.3만원, 데이터 6GB. "
        "요금제B: 월 5.5만원, 데이터 110GB. "
        "요금제C: 월 8.9만원, 데이터 무제한. 유효기간: 24개월 약정 시 할인."
    )

    # (질문, 정답) 샘플 — 실제 운영 데이터로 교체하면 됨
    samples = [
        {"q": "데이터를 많이 쓰는데 추천 요금제는?",
         "a": "요금제B (110GB, 월 5.5만원) 또는 요금제C (무제한)를 추천드립니다."},
        {"q": "가장 저렴한 요금제 뭐예요?",
         "a": "요금제A (월 3.3만원, 6GB)가 가장 저렴합니다."},
        {"q": "약정 없이 쓸 수 있나요?",
         "a": "가능합니다. 단, 24개월 약정 시 할인 혜택이 적용됩니다."},
        {"q": "요금제B와 C의 차이는?",
         "a": "요금제B는 110GB 제한, 요금제C는 완전 무제한 데이터입니다."},
    ]

    record = {
        "version": "bedrock-2026-05-14",
        "templateId": "plan-advisor-v1",
        "promptTemplate": (
            "당신은 통신사 상담 AI입니다.\n"
            "요금제 정보:\n{{plan_info}}\n\n"
            "고객 질문:\n{{question}}\n\n"
            "답변:"
        ),
        "customEvaluationMetricLabel": "plan_answer_quality",
        "customLLMJConfig": {
            "customLLMJPrompt": (
                "아래 응답이 고객 질문에 정확하고 친절하게 답했는지 평가하세요.\n"
                "프롬프트: {{prompt}}\n응답: {{response}}\n정답: {{referenceResponse}}\n"
                "1~5점 척도: 1=매우 나쁨, 5=매우 좋음. 점수만 숫자로 출력하세요."
            ),
            "customLLMJModelId": "anthropic.claude-sonnet-4-6",
        },
        "evaluationSamples": [
            {
                "inputVariables": [
                    {"plan_info": PLAN_INFO},
                    {"question": s["q"]},
                ],
                "referenceResponse": s["a"],
            }
            for s in samples
        ],
    }

    out_path = "advpo_input.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"  JSONL 파일 생성: {out_path}")
    print(f"  샘플 수: {len(record['evaluationSamples'])}개")
    print(f"\n  【Bedrock 콘솔 실행 순서】")
    print(f"  1. Amazon Bedrock > Prompt Optimization > Advanced prompt optimization")
    print(f"  2. Target models: claude-sonnet-4-6 선택 (baseline 1개)")
    print(f"  3. S3 URI for prompt templates: s3://<버킷>/advpo/advpo_input.jsonl")
    print(f"  4. S3 output location:          s3://<버킷>/advpo/output/")
    print(f"  5. Create optimization → 약 15~20분 소요")
    print(f"\n  생성된 JSONL 미리보기:")
    print(f"  {json.dumps(record, ensure_ascii=False)[:300]}...")


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(" P2_05_prompt_optimization.py")
    print(" Bedrock Prompt Optimization 실습")
    print("=" * 60)

    step1_single_optimize()
    step2_quality_comparison()
    step3_analyze_events()
    step4_advpo_jsonl()

    print(f"\n{'=' * 60}")
    print("완료")
    print("=" * 60)
