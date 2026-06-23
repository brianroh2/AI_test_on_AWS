"""
P4_04_guardrails_create.py
────────────────────────────────────────────────────────────────────
Guardrails 챕터 04 — boto3 Guardrail 생성

04-1. 환경 설정 (bedrock / bedrock-runtime 클라이언트)
04-2. Guardrail 생성 (Standard Tier + Cross-Region)
04-3. Version 생성 (DRAFT → Version 1)
결과 → guardrail_config.json 저장 (P4_05~P4_07에서 사용)

실행:
  python3 P4_04_guardrails_create.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import json
from pathlib import Path

REGION      = "us-east-1"
MODEL_ID    = "global.anthropic.claude-sonnet-4-6"
CONFIG_FILE = Path(__file__).parent / "guardrail_config.json"

# ── 04-1. 환경 설정 ──────────────────────────────────────────────
bedrock = boto3.client("bedrock",         region_name=REGION)
runtime = boto3.client("bedrock-runtime", region_name=REGION)
print("리전:", REGION)

# ── 기존 guardrail 확인 ──────────────────────────────────────────
existing = bedrock.list_guardrails().get("guardrails", [])
for g in existing:
    if g["name"] == "telco-chatbot-guardrail":
        print(f"⚠️  기존 guardrail 발견: id={g['id']} status={g['status']}")
        print("   삭제 후 재생성하거나, 기존 ID를 guardrail_config.json에 직접 기입하세요.")
        # 기존 것 사용
        guardrail_id = g["id"]
        # version 확인
        try:
            vers = bedrock.list_guardrails(guardrailIdentifier=guardrail_id).get("guardrails", [])
            # version 1이 있는지 확인
            ver_resp = bedrock.get_guardrail(guardrailIdentifier=guardrail_id, guardrailVersion="1")
            guardrail_version = ver_resp["version"]
        except Exception:
            guardrail_version = "DRAFT"
        cfg = {"guardrail_id": guardrail_id, "guardrail_version": guardrail_version}
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        print(f"✅ guardrail_config.json 저장: {cfg}")
        exit(0)

# ── 04-2. Guardrail 생성 ─────────────────────────────────────────
print("\n[04-2] Guardrail 생성 중...")
print("  - Standard Tier + Cross-Region inference 활성화")
print("  - Content filters (HIGH), Denied topics, PII, Word filters 포함")

resp = bedrock.create_guardrail(
    name="telco-chatbot-guardrail",
    description="통신사 챗봇 안전 필터 — Standard Tier",

    # Standard Tier Cross-Region 활성화 (guardrail profile)
    crossRegionConfig={
        "guardrailProfileIdentifier": "us.guardrail.v1:0"
    },

    # 유해 콘텐츠 필터 (Standard Tier)
    contentPolicyConfig={
        "filtersConfig": [
            {"type": "HATE",         "inputStrength": "HIGH", "outputStrength": "HIGH"},
            {"type": "INSULTS",      "inputStrength": "HIGH", "outputStrength": "HIGH"},
            {"type": "SEXUAL",       "inputStrength": "HIGH", "outputStrength": "HIGH"},
            {"type": "VIOLENCE",     "inputStrength": "HIGH", "outputStrength": "HIGH"},
            {"type": "MISCONDUCT",   "inputStrength": "HIGH", "outputStrength": "HIGH"},
            # ⚠️ PROMPT_ATTACK: outputStrength 반드시 NONE (입력 전용 정책)
            {"type": "PROMPT_ATTACK","inputStrength": "HIGH", "outputStrength": "NONE"},
        ],
        "tierConfig": {"tierName": "STANDARD"},  # Standard Tier
    },

    # 금지 주제 (Standard Tier)
    # ⚠️ name은 ASCII만 허용 [0-9a-zA-Z_ !?.]+
    topicPolicyConfig={
        "topicsConfig": [
            {
                "name": "Investment Advice",   # ASCII만 가능
                "definition": "주식, 펀드, 가상화폐 등 금융 투자 관련 조언 및 추천",
                "examples": [
                    "삼성전자 주식 지금 사야 할까요?",
                    "비트코인 지금 투자해도 될까요?"
                ],
                "type": "DENY",
            }
        ],
        "tierConfig": {"tierName": "STANDARD"},
    },

    # 단어 필터 (관리형 욕설 + 커스텀)
    wordPolicyConfig={
        "managedWordListsConfig": [{"type": "PROFANITY"}],
        "wordsConfig": [
            {"text": "바보"},
            {"text": "멍청이"},
        ],
    },

    # 민감 정보(PII) 필터
    # ⚠️ 콘솔 UI: "Mask" = API: "ANONYMIZE", 콘솔 UI: "Block" = API: "BLOCK"
    # boto3 SDK: action(필수) + inputAction + outputAction 모두 지정해야 콘솔에서 정상 표시됨
    sensitiveInformationPolicyConfig={
        "piiEntitiesConfig": [
            {
                "type": "PHONE",
                "action": "ANONYMIZE",        # SDK 필수 필드
                "inputAction": "ANONYMIZE",   # 입력에서 마스킹 (콘솔: Mask)
                "outputAction": "ANONYMIZE",  # 출력에서 마스킹
            },
            {
                "type": "EMAIL",
                "action": "ANONYMIZE",
                "inputAction": "ANONYMIZE",
                "outputAction": "ANONYMIZE",
            },
            {
                "type": "CREDIT_DEBIT_CARD_NUMBER",
                "action": "BLOCK",            # SDK 필수 필드
                "inputAction": "BLOCK",       # 입력에서 차단 (콘솔: Block)
                "outputAction": "BLOCK",      # 출력에서 차단
            },
        ],
        # 주민등록번호 — 표준 PII 없음, regex로 추가
        "regexesConfig": [
            {
                "name": "주민등록번호",
                "pattern": r"\d{6}-\d{7}",   # raw string: 이스케이프 불필요
                "action": "ANONYMIZE",
                "inputAction": "ANONYMIZE",
                "outputAction": "ANONYMIZE",
                "description": "한국 주민등록번호 패턴",
            }
        ],
    },

    # 차단 메시지
    blockedInputMessaging="죄송합니다, 해당 질문에는 답변 드리기 어렵습니다.",
    blockedOutputsMessaging="죄송합니다, 해당 내용은 제공하기 어렵습니다.",
)

guardrail_id = resp["guardrailId"]
print(f"  Guardrail ID: {guardrail_id}")

# ── 04-3. Version 생성 ───────────────────────────────────────────
print("\n[04-3] Version 생성 중 (DRAFT → Version 1)...")
ver = bedrock.create_guardrail_version(
    guardrailIdentifier=guardrail_id,
    description="v1 실습용",
)
guardrail_version = ver["version"]   # "1"
print(f"  Version: {guardrail_version}")

# ── config 저장 ──────────────────────────────────────────────────
cfg = {
    "guardrail_id":      guardrail_id,
    "guardrail_version": guardrail_version,
}
CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
print(f"\n✅ guardrail_config.json 저장 완료")
print(f"   {cfg}")
print(f"\n   → P4_05~P4_07에서 자동으로 로드합니다.")
