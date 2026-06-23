"""
P4_02_guardrails_console.py
────────────────────────────────────────────────────────────────────
Guardrails 챕터 02 — Guardrail 생성 (AWS Console 가이드)

이 파일은 Console에서 Guardrail을 수동 생성하는 단계별 가이드를 출력합니다.
boto3 자동 생성은 P4_04 를 사용하세요.

실행:
  python3 P4_02_guardrails_console.py
────────────────────────────────────────────────────────────────────
"""

REGION  = "us-east-1"
CONSOLE = f"https://{REGION}.console.aws.amazon.com"

print("=" * 65)
print("  Part 4-02 — Guardrail 생성 (AWS Console 7단계)")
print("=" * 65)
print(f"\n  접속 URL: {CONSOLE}/bedrock/home?region={REGION}#/guardrails")
print("  경로: Amazon Bedrock > Guardrails > Create guardrail\n")

print("─" * 65)
print("  Step 1. Provide guardrail details (기본 정보 입력)")
print("─" * 65)
print("""
  1) Name          : telco-chatbot-guardrail
  2) Description   : 통신사 챗봇 안전 필터 (선택 입력)
  3) Messaging for blocked prompts  : 죄송합니다, 해당 질문에는 답변 드리기 어렵습니다.
  4) Messaging for blocked responses: 죄송합니다, 해당 내용은 제공하기 어렵습니다.

  ⚠️  중요: Cross-Region inference 체크박스를 ON 해야 합니다.
      → "Enable cross-Region inference" 체크 후 저장
      → 이것을 먼저 하지 않으면 Standard Tier 선택 불가
      → 오류 메시지: "Can't configure guardrail policy tier.
                      Enable cross-Region inference for your guardrail
                      to use Standard tier."
""")

print("─" * 65)
print("  Step 2. Configure content filters (유해 콘텐츠 필터)")
print("─" * 65)
print("""
  1) Harmful categories → "Configure harmful categories filters" 클릭
  2) 아래 항목 모두 HIGH 설정:
     - Hate         → Input: HIGH / Output: HIGH
     - Insults      → Input: HIGH / Output: HIGH
     - Sexual       → Input: HIGH / Output: HIGH
     - Violence     → Input: HIGH / Output: HIGH
     - Misconduct   → Input: HIGH / Output: HIGH
     - Prompt attacks → Input: HIGH / Output: NONE
       ⚠️  Prompt attacks는 Output 적용 불가 → NONE 선택

  3) Content filters tier → Standard 선택
     (Standard가 보이지 않으면 Step1의 Cross-Region inference 먼저 체크)
""")

print("─" * 65)
print("  Step 3. Add denied topics (금지 주제) — optional")
print("─" * 65)
print("""
  1) "Add denied topic" 클릭
  2) 항목 입력:
     - Name       : Investment Advice
       ⚠️  ASCII 문자만 허용 (한글 입력 시 ValidationException 발생)
     - Definition : 주식, 펀드, 가상화폐 등 금융 투자 관련 조언 및 추천
       (Definition·Examples는 한국어 가능)
     - Sample phrases: 삼성전자 주식 지금 사야 할까요?,
                       비트코인 지금 투자해도 될까요?
     - Type: DENY

  3) Denied topics tier → Standard 선택
""")

print("─" * 65)
print("  Step 4. Add word filters (단어 필터) — optional")
print("─" * 65)
print("""
  1) Profanity filter → "Filter profanity" 체크 ON
     (영어 욕설 위주, 한국어는 Content filter가 담당)
  2) Custom words → "Add custom words and phrases" 클릭
     추가 단어 예시: 바보, 멍청이
     (각 단어 입력 후 Enter)
""")

print("─" * 65)
print("  Step 5. Add sensitive information filters (PII) — optional")
print("─" * 65)
print("""
  1) "Add new PII" 클릭 → PII Type 선택, Input/Output, Block/Mask 설정

  권장 설정:
  ┌─────────────────────────┬──────────┬────────────┐
  │ PII Type                │ Action   │ I/O        │
  ├─────────────────────────┼──────────┼────────────┤
  │ Phone (전화번호)         │ Anonymize│ Input+Output│
  │ Email (이메일)           │ Anonymize│ Input+Output│
  │ Credit/Debit card number│ Block    │ Input+Output│
  └─────────────────────────┴──────────┴────────────┘

  2) 주민등록번호 (표준 PII에 없음) → regex pattern 추가:
     - "Add regex pattern" 클릭
     - Name   : 주민등록번호
     - Pattern: \\d{6}-\\d{7}
       ⚠️  raw string: 백슬래시 그대로 입력 (이스케이프 불필요)
     - Action : Anonymize
""")

print("─" * 65)
print("  Step 6. Add contextual grounding check — 건너뜀")
print("─" * 65)
print("""
  → 영어 위주 동작, 한국어 챗봇 환경에서는 효과 미미
  → Next로 건너뜁니다.
""")

print("─" * 65)
print("  Step 7. Review and create (검토 및 생성)")
print("─" * 65)
print("""
  1) "Create guardrail" 클릭 → Draft 버전 생성
  2) 상세 화면에서 "Create version" 클릭
     → Version description: v1 실습용
     → Version 번호: 1 (자동 부여)
  3) 생성 후 다음 정보를 메모하세요:
     ┌─────────────────┬───────────────────────────┐
     │ Guardrail ID    │ (예: abcd1234efgh)         │
     │ Guardrail Version│ 1                         │
     └─────────────────┴───────────────────────────┘
     → P4_04~P4_07 코드에 자동 로드됩니다 (guardrail_config.json)
""")

print("─" * 65)
print("  확인 사항 체크리스트")
print("─" * 65)
print("""
  □ Cross-Region inference 체크박스 ON
  □ Standard Tier 선택됨
  □ Content filters 모두 HIGH
  □ Prompt attacks Output = NONE
  □ Denied topics Name = ASCII (Investment Advice)
  □ PII: PHONE/EMAIL Anonymize, CREDIT_CARD Block
  □ 주민등록번호 regex 패턴 추가
  □ Create version 완료 → ID + Version 메모
""")

print("  ℹ️  boto3 자동 생성을 원하면 → python3 P4_04_guardrails_create.py")
print("=" * 65)
