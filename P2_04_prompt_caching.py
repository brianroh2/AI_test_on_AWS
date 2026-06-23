"""
P2_04_prompt_caching.py
────────────────────────────────────────────────────────────────────
주제: Bedrock Prompt Caching — 긴 컨텍스트 재사용으로 비용/속도 절감

두 가지 API 방식을 비교:
  A) Bedrock Converse  — system/messages에 cachePoint 마커 삽입
  B) Bedrock InvokeModel (raw body) — cache_control: ephemeral 지정

캐싱 동작 확인:
  - 1회 호출: cacheWriteInputTokens > 0  (캐시 저장)
  - 2회 이후: cacheReadInputTokens > 0   (캐시 적중)
  - 비용 비교: write≈일반비용×1.25, read≈일반비용×0.1 (약 90% 절감)

실행:
  python3 P2_04_prompt_caching.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import json
import time

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)

SEP = "─" * 60

# 캐싱 효과를 보려면 긴 문서가 필요 (최소 ~1000 토큰)
LONG_DOC = (
    "【가상 통신사 요금제 전체 안내서】\n"
    + (
        "요금제명: 스마트 베이직 | 월정액: 33,000원 | 데이터: 11GB | 통화: 무제한 | 문자: 무제한\n"
        "요금제명: 스마트 미디엄 | 월정액: 44,000원 | 데이터: 33GB | 통화: 무제한 | 문자: 무제한\n"
        "요금제명: 5G 스탠다드  | 월정액: 55,000원 | 데이터: 55GB | 통화: 무제한 | 문자: 무제한\n"
        "요금제명: 5G 프리미엄  | 월정액: 69,000원 | 데이터: 110GB| 통화: 무제한 | 문자: 무제한\n"
        "요금제명: 5G 무제한    | 월정액: 89,000원 | 데이터: 완전 무제한 | 통화: 무제한 | 부가서비스: OTT 포함\n"
    ) * 60   # 반복해 충분한 길이 확보
)


# ═══════════════════════════════════════════════════════════════
# STEP 1: 캐싱 없는 일반 호출 (기준선)
# ═══════════════════════════════════════════════════════════════
def step1_no_cache(question: str) -> dict:
    print(f"\n  질문: {question}")
    t0 = time.time()
    resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": LONG_DOC}],          # cachePoint 없음
        messages=[{"role": "user", "content": [{"text": question}]}],
        inferenceConfig={"maxTokens": 150},
    )
    elapsed = time.time() - t0
    usage   = dict(resp["usage"])
    answer  = resp["output"]["message"]["content"][0]["text"].strip()
    print(f"  응답: {answer[:120]}...")
    print(f"  토큰: {usage}")
    print(f"  소요: {elapsed:.2f}초")
    return {"usage": usage, "elapsed": elapsed}


# ═══════════════════════════════════════════════════════════════
# STEP 2-A: Bedrock Converse — cachePoint 방식
# ═══════════════════════════════════════════════════════════════
def step2a_converse_cache(question: str) -> dict:
    t0 = time.time()
    resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[
            {"text": LONG_DOC},
            {"cachePoint": {"type": "default"}},   # ← 이 위치까지 캐시
        ],
        messages=[{"role": "user", "content": [{"text": question}]}],
        inferenceConfig={"maxTokens": 150},
    )
    elapsed = time.time() - t0
    usage   = dict(resp["usage"])
    answer  = resp["output"]["message"]["content"][0]["text"].strip()
    print(f"  응답: {answer[:120]}...")
    print(f"  토큰: {usage}")
    print(f"  소요: {elapsed:.2f}초")
    return {"usage": usage, "elapsed": elapsed}


# ═══════════════════════════════════════════════════════════════
# STEP 2-B: Bedrock InvokeModel raw body — cache_control 방식
# ═══════════════════════════════════════════════════════════════
def step2b_invoke_model_cache(question: str) -> dict:
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 150,
        "system": [
            {
                "type": "text",
                "text": LONG_DOC,
                "cache_control": {"type": "ephemeral"},   # ← cache_control 방식
            }
        ],
        "messages": [{"role": "user", "content": question}],
    }
    t0   = time.time()
    resp = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(body),
    )
    elapsed = time.time() - t0
    result  = json.loads(resp["body"].read())
    usage   = result["usage"]
    answer  = result["content"][0]["text"].strip()
    print(f"  응답: {answer[:120]}...")
    print(f"  토큰: {usage}")
    print(f"  소요: {elapsed:.2f}초")
    return {"usage": usage, "elapsed": elapsed}


# ═══════════════════════════════════════════════════════════════
# STEP 3: 멀티턴 캐싱 — messages 내 cachePoint
# ═══════════════════════════════════════════════════════════════
def step3_multiturn_cache():
    print(f"\n{SEP}")
    print("【STEP 3】 멀티턴 대화에서 메시지 캐싱")
    print(SEP)
    print("  대화 히스토리가 길어질 때 messages에도 cachePoint 삽입 가능\n")

    history = [
        {"role": "user",      "content": [{"text": "5G 스탠다드 요금제 설명해줘."}]},
        {"role": "assistant", "content": [{"text": "5G 스탠다드는 월 55,000원에 데이터 55GB를 제공합니다."}]},
        {"role": "user",      "content": [{"text": "5G 프리미엄과 비교하면?"}]},
        {"role": "assistant", "content": [{"text": "5G 프리미엄은 월 69,000원에 110GB — 두 배 용량입니다."}]},
        # ↓ 여기까지 캐시 (이미 나눈 대화)
        {"role": "user", "content": [
            {"text": "위 두 요금제 중 영상 스트리밍에 더 적합한 건?"},
            {"cachePoint": {"type": "default"}},   # messages 안에도 삽입 가능
        ]},
    ]

    t0 = time.time()
    resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": LONG_DOC}, {"cachePoint": {"type": "default"}}],
        messages=history,
        inferenceConfig={"maxTokens": 150},
    )
    elapsed = time.time() - t0
    usage   = dict(resp["usage"])
    answer  = resp["output"]["message"]["content"][0]["text"].strip()

    print(f"  응답: {answer[:200]}")
    print(f"  토큰: {usage}")
    print(f"  소요: {elapsed:.2f}초")
    print(f"\n  💡 cachePoint는 system과 messages 양쪽 모두에 삽입 가능")


# ═══════════════════════════════════════════════════════════════
# STEP 4: 비용 비교 테이블 출력
# ═══════════════════════════════════════════════════════════════
def step4_cost_summary(no_cache_results: list, cached_results: list):
    print(f"\n{SEP}")
    print("【STEP 4】 캐싱 효과 종합 비교")
    print(SEP)

    def token_label(usage: dict) -> str:
        if isinstance(usage, dict):
            inp   = usage.get("inputTokens",           usage.get("input_tokens", 0))
            write = usage.get("cacheWriteInputTokens",  usage.get("cache_creation_input_tokens", 0))
            read  = usage.get("cacheReadInputTokens",   usage.get("cache_read_input_tokens", 0))
            out   = usage.get("outputTokens",           usage.get("output_tokens", 0))
            return f"입력={inp}, 캐시쓰기={write}, 캐시읽기={read}, 출력={out}"
        return str(usage)

    print(f"\n  {'호출':8s} {'방식':16s} {'소요(초)':10s} {'토큰 상세'}")
    print(f"  {'─'*8} {'─'*16} {'─'*10} {'─'*50}")

    for i, r in enumerate(no_cache_results, 1):
        print(f"  {i}회     {'캐싱 없음':16s} {r['elapsed']:8.2f}초  {token_label(r['usage'])}")

    print()
    for i, r in enumerate(cached_results, 1):
        u   = r["usage"]
        read = u.get("cacheReadInputTokens", u.get("cache_read_input_tokens", 0))
        tag  = "캐시 쓰기" if i == 1 else "캐시 읽기 ✅"
        print(f"  {i}회     {tag:16s} {r['elapsed']:8.2f}초  {token_label(u)}")
        if i >= 2 and read > 0:
            print(f"          → cacheRead {read}토큰 = 일반 대비 약 90% 비용 절감")

    print(f"\n  💡 비용 공식 (Sonnet 4.6 기준 근사)")
    print(f"     일반 입력     : $3.00 / 1M tokens")
    print(f"     캐시 쓰기 비용: $3.75 / 1M tokens  (약 1.25× — 최초 1회만 발생)")
    print(f"     캐시 읽기 비용: $0.30 / 1M tokens  (약 0.1× — 2회차부터 90% 절감)")
    print(f"     TTL          : 기본 5분 (모델 응답 간격 기준)")


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(" P2_04_prompt_caching.py")
    print(" Bedrock Prompt Caching 비교 실습")
    print("=" * 60)

    QUESTION = "가장 저렴한 요금제와 가장 비싼 요금제의 차이점은?"

    # ── STEP 1: 캐싱 없는 기준선 2회 호출 ──────────────────────
    print(f"\n{SEP}")
    print("【STEP 1】 캐싱 없음 — 기준선 (2회 호출)")
    print(SEP)
    no_cache_1 = step1_no_cache(QUESTION)
    no_cache_2 = step1_no_cache(QUESTION)

    # ── STEP 2-A: Converse cachePoint (2회 호출) ────────────────
    print(f"\n{SEP}")
    print("【STEP 2-A】 Converse cachePoint — 1회(캐시 쓰기) / 2회(캐시 읽기)")
    print(SEP)
    print(f"\n  1회 호출 (캐시 저장):")
    cache_a_1 = step2a_converse_cache(QUESTION)
    print(f"\n  2회 호출 (캐시 적중 기대):")
    cache_a_2 = step2a_converse_cache(QUESTION)

    # ── STEP 2-B: InvokeModel cache_control ─────────────────────
    print(f"\n{SEP}")
    print("【STEP 2-B】 InvokeModel cache_control — raw body 방식")
    print(SEP)
    print(f"\n  1회 호출 (캐시 저장):")
    cache_b_1 = step2b_invoke_model_cache(QUESTION)
    print(f"\n  2회 호출 (캐시 적중 기대):")
    cache_b_2 = step2b_invoke_model_cache(QUESTION)

    # ── STEP 2-A vs 2-B 키 이름 차이 설명 ──────────────────────
    print(f"\n{SEP}")
    print("【2-A vs 2-B 토큰 키 이름 비교】")
    print(SEP)
    print(f"  Converse (cachePoint)  : cacheWriteInputTokens / cacheReadInputTokens")
    print(f"  InvokeModel (cache_control): cache_creation_input_tokens / cache_read_input_tokens")
    print(f"  → 같은 기능, 다른 API 키 이름 — 혼동 주의!")

    # ── STEP 3: 멀티턴 캐싱 ─────────────────────────────────────
    step3_multiturn_cache()

    # ── STEP 4: 비용 비교 요약 ───────────────────────────────────
    step4_cost_summary(
        no_cache_results=[no_cache_1, no_cache_2],
        cached_results=[cache_a_1, cache_a_2],
    )

    print(f"\n{'=' * 60}")
    print("완료")
    print("=" * 60)
