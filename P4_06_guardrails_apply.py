"""
P4_06_guardrails_apply.py
────────────────────────────────────────────────────────────────────
Guardrails 챕터 06 — ApplyGuardrail API

06-1. apply_guardrail — 입력/출력 독립 필터링
06-2. 사전 필터링 (INPUT 검사 → 통과 시 Converse 호출)

ApplyGuardrail 은 Converse 없이 텍스트를 직접 Guardrail에 전달합니다.
→ 용도: 사용자 입력 사전 검증, 외부 API 결과 사후 검증

실행:
  python3 P4_06_guardrails_apply.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import json
from pathlib import Path

REGION      = "us-east-1"
MODEL_ID    = "global.anthropic.claude-sonnet-4-6"
CONFIG_FILE = Path(__file__).parent / "guardrail_config.json"

runtime = boto3.client("bedrock-runtime", region_name=REGION)

# ── config 로드 ──────────────────────────────────────────────────
if not CONFIG_FILE.exists():
    print("❌ guardrail_config.json 없음 — P4_04 먼저 실행하세요.")
    exit(1)

cfg               = json.loads(CONFIG_FILE.read_text())
guardrail_id      = cfg["guardrail_id"]
guardrail_version = cfg["guardrail_version"]
print(f"Guardrail ID: {guardrail_id}  Version: {guardrail_version}")


# ── 06-1. apply_guardrail 함수 ───────────────────────────────────
def check(text: str, source: str = "INPUT") -> dict:
    """
    텍스트를 Guardrail 에 직접 전달.
    source: "INPUT"(사용자 입력) 또는 "OUTPUT"(모델 출력)
    반환: {"action": "NONE"|"GUARDRAIL_INTERVENED", "outputs": [...]}
    """
    resp = runtime.apply_guardrail(
        guardrailIdentifier=guardrail_id,
        guardrailVersion=guardrail_version,
        source=source,          # ⚠️ "INPUT" 또는 "OUTPUT" 만 허용
        # ⚠️ content 형식: [{"text": {"text": "..."}}]
        content=[{"text": {"text": text}}],
    )
    return {
        "action":  resp["action"],          # "NONE" or "GUARDRAIL_INTERVENED"
        "outputs": resp.get("outputs", [])  # 마스킹 결과 포함
    }


print("\n" + "=" * 60)
print("  [06-1] apply_guardrail 직접 호출 테스트")
print("=" * 60)

samples = [
    ("정상 질문",       "5GX 요금제 월 요금은 얼마인가요?",         "INPUT"),
    ("욕설 입력",       "너 진짜 멍청하구나",                        "INPUT"),
    ("PII — 전화번호",  "제 번호는 010-1234-5678입니다",             "INPUT"),
    ("금지 주제",       "비트코인 지금 투자해도 될까요?",             "INPUT"),
    ("출력 필터 테스트","당신의 이메일은 test@example.com 입니다",   "OUTPUT"),
]

for label, text, src in samples:
    result = check(text, source=src)
    action = result["action"]
    icon   = "🚫" if action == "GUARDRAIL_INTERVENED" else "✅"
    out_text = ""
    if result["outputs"]:
        out_text = result["outputs"][0].get("text", "")[:80]
    print(f"\n  [{label}] source={src}")
    print(f"  입력  : {text}")
    print(f"  action: {icon} {action}")
    if out_text and out_text != text:
        print(f"  출력  : {out_text}")  # 마스킹된 경우 변환된 텍스트


# ── 06-2. 사전 필터링 — INPUT 검사 후 Converse ──────────────────
print("\n" + "=" * 60)
print("  [06-2] 사전 필터링 패턴")
print("  (ApplyGuardrail INPUT → 통과 시 Converse 호출)")
print("=" * 60)

def ask_prefiltered(user_text: str) -> str:
    """
    1) ApplyGuardrail(INPUT) 으로 사전 검사
    2) 차단 → Guardrail 차단 메시지 반환 (Converse 호출 없음)
    3) 통과 → Converse 호출 → 응답 반환
    """
    pre = check(user_text, source="INPUT")
    if pre["action"] == "GUARDRAIL_INTERVENED":
        blocked_msg = pre["outputs"][0]["text"] if pre["outputs"] else "죄송합니다, 답변 드리기 어렵습니다."
        return f"[사전 차단] {blocked_msg}"

    resp = runtime.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": user_text}]}],
        inferenceConfig={"maxTokens": 400},
    )
    return resp["output"]["message"]["content"][0]["text"]


pre_tests = [
    "LTE 요금제 중 가장 저렴한 것은?",
    "삼성전자 주식 사야 할까요?",
]

for q in pre_tests:
    print(f"\n  질문: {q}")
    answer = ask_prefiltered(q)
    print(f"  응답: {answer[:120]}")

print(f"""
  ─────────────────────────────────────────────
  Converse(05) vs ApplyGuardrail(06) 비교:

  Converse    → 모델 호출 + Guardrail 동시 적용
               guardContent 로 감싸기 필수

  ApplyGuardrail → 모델 호출 없이 텍스트만 검사
                   source: INPUT/OUTPUT 지정 가능
                   용도: 사전/사후 독립 필터링
                   비용: Converse 없으므로 저렴
  ─────────────────────────────────────────────
""")
