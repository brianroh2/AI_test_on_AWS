"""
P4_01_guardrails_setup.py
────────────────────────────────────────────────────────────────────
Guardrails 챕터 01 — 사전준비 (리전, IAM, Tier, 모델 확인)

실행:
  python3 P4_01_guardrails_setup.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import json

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"
CONSOLE  = f"https://{REGION}.console.aws.amazon.com"

bedrock  = boto3.client("bedrock",         region_name=REGION)
runtime  = boto3.client("bedrock-runtime", region_name=REGION)
sts      = boto3.client("sts",             region_name=REGION)

print("=" * 60)
print("  Part 4 — Guardrails 사전 환경 확인")
print("=" * 60)

# 1. 계정/리전
identity = sts.get_caller_identity()
print(f"\n[1] 계정 정보")
print(f"    계정 ID : {identity['Account']}")
print(f"    ARN     : {identity['Arn']}")
print(f"    리전    : {REGION}")

# 2. Guardrails API 접근
print(f"\n[2] Guardrails API 접근")
try:
    resp = bedrock.list_guardrails(maxResults=5)
    existing = resp.get("guardrails", [])
    print(f"    ✅ list_guardrails 성공 — 기존 Guardrail {len(existing)}개")
    for g in existing:
        print(f"       - {g['name']} (id={g['id']}, status={g['status']})")
except Exception as e:
    print(f"    ❌ list_guardrails 실패: {e}")

# 3. CreateGuardrail 권한
print(f"\n[3] bedrock:CreateGuardrail 권한")
try:
    bedrock.create_guardrail(
        name="_perm_check_dummy_",
        blockedInputMessaging="blocked",
        blockedOutputsMessaging="blocked",
    )
    print("    ✅ 권한 있음")
except Exception as e:
    err = str(e)
    if "AccessDeniedException" in err:
        print("    ❌ 권한 없음 — IAM 정책 추가 필요")
    else:
        print(f"    ✅ 권한 있음 (ValidationException = 더미값 오류, 권한은 OK)")

# 4. ApplyGuardrail 권한
print(f"\n[4] bedrock:ApplyGuardrail 권한")
try:
    runtime.apply_guardrail(
        guardrailIdentifier="dummy",
        guardrailVersion="DRAFT",
        source="INPUT",
        content=[{"text": {"text": "test"}}]
    )
except Exception as e:
    err = str(e)
    if "AccessDeniedException" in err:
        print("    ❌ 권한 없음 — IAM 정책 추가 필요")
    else:
        print(f"    ✅ 권한 있음 (오류 유형: {type(e).__name__})")

# 5. 모델 확인
print(f"\n[5] 모델 확인: {MODEL_ID}")
try:
    resp = runtime.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": "안녕"}]}],
        inferenceConfig={"maxTokens": 20},
    )
    print(f"    ✅ 모델 정상 동작")
except Exception as e:
    print(f"    ❌ 모델 오류: {e}")

# 6. Tier 안내
print(f"""
[6] Guardrails Tier 안내
    ┌──────────┬────────────────────────────────────────────────┐
    │ Classic  │ 기본 content filter (한국어 제한적)            │
    │ Standard │ content filter HIGH + denied topics + PII 등  │
    │          │ ⚠️  Cross-Region inference 먼저 활성화 필요    │
    └──────────┴────────────────────────────────────────────────┘
    → 이 실습은 Standard Tier 사용 (P4_02/P4_04에서 설정)
""")

# 7. IAM 정책 참고
ACCOUNT_ID = identity["Account"]
print(f"[7] Standard Tier IAM Resource 예시")
print(f"""    {{
      "Effect": "Allow",
      "Action": ["bedrock:CreateGuardrail", "bedrock:CreateGuarailVersion",
                 "bedrock:GetGuardrail", "bedrock:ListGuardrails",
                 "bedrock:ApplyGuardrail", "bedrock:InvokeModel"],
      "Resource": [
        "arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:guardrail/*",
        "arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:guardrail-profile/us.guardrail.v1:0",
        "arn:aws:bedrock:us-west-2:{ACCOUNT_ID}:guardrail-profile/us.guardrail.v1:0"
      ]
    }}""")

# 8. Console 링크
print(f"\n[8] Console 링크")
print(f"    Guardrails : {CONSOLE}/bedrock/home?region={REGION}#/guardrails")
print(f"    IAM Roles  : https://console.aws.amazon.com/iam/home#/roles")

print("\n" + "=" * 60)
print("  사전준비 확인 완료 → P4_02 또는 P4_04로 진행하세요")
print("=" * 60)
