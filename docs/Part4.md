# Part 4 — Amazon Bedrock Guardrails 학습 가이드

## 개요
Guardrails는 AWS가 제공하는 **LLM 안전 필터 레이어**입니다.
애플리케이션 코드를 수정하지 않고 욕설·금지 주제·PII·프롬프트 공격을 일괄 차단합니다.

---

## AWS 브라우저(콘솔)에서 확인할 부분

| 확인 항목 | 경로 | 무엇을 보는가 |
|-----------|------|--------------|
| Guardrail 목록 | Bedrock → Safeguards → Guardrails | 생성된 Guardrail ID, 버전, 상태 |
| 정책 상세 | Guardrail 클릭 → 각 탭 | Content filters, Topics, Word filters, PII, Grounding |
| 테스트 UI | Guardrail → Test | 텍스트 입력 → 실시간 차단/통과 확인 |
| 사용량 | CloudWatch → Bedrock 메트릭 | GuardrailInvocations, BlockedCount |

> **포인트**: 콘솔 Test 탭에서 직접 텍스트를 입력하면 코드 없이 즉시 동작을 확인할 수 있습니다.

---

## 파일별 핵심 내용 및 연관성

```
P4_01_guardrails_setup.py
  └─ IAM 권한/리전 확인 → 이후 모든 P4 파일의 전제조건

P4_02_guardrails_console.py
  └─ 콘솔 가이드 출력 → AWS UI에서 수동으로 Guardrail 생성하는 절차 안내

P4_03_guardrails_test_console.py
  └─ 콘솔 테스트 가이드 → Test 탭 사용법

P4_04_guardrails_create.py        ← 핵심
  └─ boto3로 Guardrail 자동 생성 → guardrail_config.json 저장
  └─ P4_05, P4_06, P4_07의 실행 전제 (config 파일 생성)

P4_05_guardrails_converse.py      ← 핵심
  └─ guardContent 래핑 + guardrailConfig 파라미터 실습
  └─ P4_05_guardrails_converse_streamlit.py 의 원본

P4_06_guardrails_apply.py
  └─ 실제 서비스(챗봇)에 Guardrail 붙이는 패턴 실습

P4_07_guardrails_chatbot.py
  └─ Streamlit 챗봇 + Guardrail 통합 (대화형 검증)

P4_05_guardrails_converse_streamlit.py  ← 시각화 추가
  └─ 차단/통과 결과를 색상 배지로 시각화
  └─ 트리거된 정책(content filter, topic, PII 등) 배지 표시
  └─ 전체 이력 테이블 (여러 케이스 비교)
```

---

## 코드에서 중요한 부분

### 1. `guardContent` 래핑 — 반드시 필요
```python
# ❌ 이렇게 하면 Guardrail 검사 안 됨
"content": [{"text": {"text": user_input}}]

# ✅ guardContent로 감싸야 Guardrail 검사 대상
"content": [{"guardContent": {"text": {"text": user_input}}}]
```

### 2. `stopReason` 으로 차단 판단
```python
blocked = resp["stopReason"] == "guardrail_intervened"
```

### 3. `trace="enabled"` — 어느 정책이 걸렸는지 확인
```python
guardrailConfig={
    "guardrailIdentifier": guardrail_id,
    "guardrailVersion":    guardrail_version,
    "trace":               "enabled",  # inputAssessment / outputAssessment 반환
}
```

### 4. 스트리밍 + Guardrail: `streamProcessingMode: "sync"` 필수
```python
guardrailConfig={
    ...
    "streamProcessingMode": "sync",  # 필터 적용 후 스트리밍 (async면 필터 전 먼저 흘러나올 수 있음)
}
```

---

## AWS만의 장점

| 장점 | 설명 |
|------|------|
| **코드 변경 없는 정책 업데이트** | Guardrail 내용을 콘솔에서 수정하면 즉시 반영 — 재배포 불필요 |
| **멀티 레이어 보호** | 입력(Input) + 출력(Output) 양방향 동시 검사 |
| **PII 자동 마스킹** | 전화번호·이메일·카드번호를 코드 없이 `[PHONE]` 등으로 자동 치환 |
| **Grounding 검사** | RAG 응답이 소스 문서에 근거하는지 자동 평가 (환각 억제) |
| **버전 관리** | 프로덕션/스테이징 버전을 별도로 유지 — A/B 테스트 가능 |
| **모든 Bedrock 모델 공통 적용** | Claude, Nova, Titan 등 모델 관계없이 동일 정책 적용 |

---

## 실행 순서

```bash
python3 P4_01_guardrails_setup.py       # 권한 점검
python3 P4_04_guardrails_create.py      # Guardrail 생성 (guardrail_config.json 생성)
python3 P4_05_guardrails_converse.py    # 터미널 테스트
streamlit run P4_05_guardrails_converse_streamlit.py \
  --server.port 8505 --server.headless true  # 시각화 테스터
streamlit run P4_07_guardrails_chatbot.py \
  --server.port 8507 --server.headless true  # 챗봇 통합
```
