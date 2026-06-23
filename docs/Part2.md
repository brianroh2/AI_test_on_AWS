# Part 2 — Amazon Bedrock API 심화 학습 가이드

## 개요
Bedrock API를 실무에서 효율적으로 활용하기 위한 **5가지 핵심 기능**을 다룹니다.
API 파라미터 구조 이해부터 프롬프트 버전 관리, 비용 절감 기법, AI 자동 최적화, 실시간 챗봇까지 순서대로 쌓이는 구조입니다.

---

## AWS 브라우저(콘솔)에서 확인할 부분

| 확인 항목 | 경로 | 무엇을 보는가 |
|-----------|------|--------------|
| Cross-region 프로파일 | Bedrock → Cross-region inference | us./global. 프로파일 목록과 라우팅 리전 |
| Prompt 목록 | Bedrock → Prompt management | 생성된 프롬프트 ID, 버전, 변수 목록 |
| Prompt Routing 설정 | Bedrock → Prompt routing | Router 목록, responseQualityDifference 값 |
| Prompt Caching 확인 | CloudWatch → Bedrock 메트릭 | cacheWriteInputTokens / cacheReadInputTokens |
| Prompt Optimization | Bedrock → Prompt optimization | 최적화 작업 이력, AdvPO 배치 결과 |
| 비용 분석 | Cost Explorer → Bedrock 필터 | 캐시 읽기/쓰기 비용 vs 일반 비용 비교 |

> **포인트**: Prompt Management 콘솔에서는 프롬프트를 직접 편집하고 버전을 배포할 수 있습니다. 코드 없이 A/B 테스트가 가능합니다.

---

## 파일별 핵심 내용 및 연관성

```
P2_01_api_params.py               ← 핵심 시작점
  └─ inferenceConfig 래퍼 필수 여부 (Converse vs Anthropic SDK 직접 비교)
  └─ MODEL_ID cross-region 접두사: us. / global. / 없음 차이
  └─ additionalModelRequestFields — Extended Thinking 활성화 전용 필드
  └─ 이후 모든 P2 파일의 API 기초 이해

P2_02_prompt_management.py        ← 핵심
  └─ 코드 하드코딩 vs Bedrock Prompt ARN 호출 직접 비교
  └─ create_prompt → create_prompt_version → ARN 발급 흐름
  └─ promptVariables로 변수값만 전달 (프롬프트 문자열 코드에 없음)
  └─ v1 → v2 업데이트 시 ARN 교체만으로 즉시 반영

P2_03_prompt_routing.py
  └─ Intelligent Prompt Router 생성 (Nova Lite + Nova Pro)
  └─ responseQualityDifference 값별 라우팅 차이 비교 (0/50/100)
  └─ 단순 질문 → Lite 자동 선택, 복잡 질문 → Pro 자동 선택
  └─ 실행 후 리소스 자동 정리 포함

P2_04_prompt_caching.py           ← 핵심 (비용 절감 핵심)
  └─ Converse cachePoint 방식 vs InvokeModel cache_control 방식 비교
  └─ 1회 호출: cacheWriteInputTokens (쓰기 비용 ×1.25)
  └─ 2회 이후: cacheReadInputTokens (읽기 비용 ×0.1 → 90% 절감)
  └─ 멀티턴 messages 안에도 cachePoint 삽입 가능

P2_05_prompt_optimization.py
  └─ optimize_prompt API — AI가 프롬프트를 자동으로 개선
  └─ analyzePromptEvent(분석 중) / optimizedPromptEvent(결과) 이벤트 스트림
  └─ Advanced Prompt Optimization(AdvPO) JSONL 데이터 생성 (배치는 콘솔 실행)
  └─ 짧고 모호한 프롬프트일수록 최적화 효과가 큼

P2_06_chatbot_streamlit.py
  └─ boto3 / Anthropic SDK / OpenAI 방식 3가지 스트리밍 비교
  └─ SDK별 독립 토큰 카운터 + 전체 누적 비교 테이블
  └─ 사이드바에서 실시간 SDK 전환 가능
```

---

## 코드에서 중요한 부분

### 1. Converse API — `inferenceConfig` 래퍼 필수
```python
# ❌ Converse에서 직접 최상위 전달 → TypeError
bedrock.converse(modelId=..., maxTokens=100, temperature=0.5, ...)

# ✅ inferenceConfig 딕셔너리 안에 넣어야 함
bedrock.converse(
    modelId=MODEL_ID,
    messages=[...],
    inferenceConfig={"maxTokens": 100, "temperature": 0.5},
)
```

### 2. MODEL_ID 접두사 — cross-region inference
```python
# 접두사 없음: 지정 리전 단일 호출 (트래픽 급증 시 ThrottlingException 위험)
"anthropic.claude-sonnet-4-6"

# us. : us-east-1 / us-west-2 자동 분산
"us.anthropic.claude-sonnet-4-6"

# global. : 전 세계 리전 자동 분산 (교재 표준)
"global.anthropic.claude-sonnet-4-6"
```

### 3. Prompt Caching — 두 API의 키 이름 차이 주의
```python
# Converse (cachePoint 방식)
system=[{"text": LONG_DOC}, {"cachePoint": {"type": "default"}}]
# 반환 키: cacheWriteInputTokens / cacheReadInputTokens

# InvokeModel (cache_control 방식)
"system": [{"type": "text", "text": LONG_DOC, "cache_control": {"type": "ephemeral"}}]
# 반환 키: cache_creation_input_tokens / cache_read_input_tokens
```

### 4. Extended Thinking — `additionalModelRequestFields` 전용
```python
# ❌ inferenceConfig에 넣으면 ValidationException
inferenceConfig={"thinking": {"type": "enabled"}}

# ✅ additionalModelRequestFields에 넣어야 함
additionalModelRequestFields={
    "thinking": {"type": "enabled", "budget_tokens": 2000}
}
# temperature는 반드시 1.0, maxTokens는 2000 이상 권장
```

### 5. Prompt Management ARN 호출 — `promptVariables`만 전달
```python
# ARN 호출 시 messages, inferenceConfig 전달 불가 → 프롬프트에 설정됨
bedrock.converse(
    modelId=prompt_arn,       # 모델 ID 대신 ARN
    promptVariables={
        "usage": {"text": "영상 스트리밍"},
        "count": {"text": "2"},
    },
)
```

---

## AWS만의 장점

| 장점 | 설명 |
|------|------|
| **Cross-region 자동 분산** | us./global. 접두사 하나로 트래픽 급증 시 자동 리전 분산 — ThrottlingException 방지 |
| **Prompt 버전 관리** | Git처럼 프롬프트를 버전으로 관리 — 롤백, A/B 테스트, 팀 협업 가능 |
| **Intelligent Routing** | 질문 복잡도를 AWS가 자동 판단해 비용 최적 모델 선택 — 코드 변경 없음 |
| **Prompt Caching** | 긴 컨텍스트 재사용 시 비용 최대 90% 절감, 응답 속도 향상 |
| **AI 프롬프트 최적화** | optimize_prompt API로 짧은 프롬프트를 구조화된 고품질 프롬프트로 자동 변환 |
| **멀티 SDK 지원** | boto3, Anthropic SDK, OpenAI 호환 방식 모두 동일 모델에 접근 가능 |

---

## 실행 순서

```bash
python3 P2_01_api_params.py           # API 파라미터 구조 이해
python3 P2_02_prompt_management.py    # 프롬프트 버전 관리
python3 P2_03_prompt_routing.py       # 자동 라우팅
python3 P2_04_prompt_caching.py       # 캐싱 비용 절감
python3 P2_05_prompt_optimization.py  # 프롬프트 자동 최적화 (2~3분 소요)
streamlit run P2_06_chatbot_streamlit.py \
  --server.port 8501 --server.headless true  # 멀티SDK 챗봇
```

> **P2_05 실행 시간**: optimize_prompt API 1회당 약 15초 소요 → 총 6회 호출로 2~3분 정상

---

## 비용 절감 요약

| 기능 | 절감 효과 | 적용 조건 |
|------|----------|----------|
| Prompt Caching | 반복 입력 최대 **90% 절감** | 동일 컨텍스트 재사용, TTL 5분 이내 |
| Prompt Routing | 단순 질문 비용 **~70% 절감** | Nova Lite vs Nova Pro 가격 차이 활용 |
| Cross-region | 직접적 절감은 없으나 **가용성 향상** | ThrottlingException으로 인한 재시도 비용 방지 |
