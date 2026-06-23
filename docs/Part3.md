# Part 3 — Amazon Bedrock Knowledge Base (RAG) 학습 가이드

## 개요
RAG(Retrieval-Augmented Generation)는 LLM의 **지식 한계를 문서 검색으로 보완**하는 패턴입니다.
Bedrock Knowledge Base는 S3 문서 → 벡터 인덱스 → 자동 검색 파이프라인을 완전 관리형으로 제공합니다.

이 파트에서는 **텍스트 KB**와 **멀티모달 KB** 두 가지를 실습합니다.

---

## AWS 브라우저(콘솔)에서 확인할 부분

| 확인 항목 | 경로 | 무엇을 보는가 |
|-----------|------|--------------|
| S3 버킷 | S3 → telco-rateplan-kb-* | PDF 업로드 확인 (text/ multimodal/ 프리픽스) |
| KB 목록 | Bedrock → Knowledge bases | KB 이름, 상태(ACTIVE), 데이터 소스 |
| KB 생성 단계 | KB → Create knowledge base | 파서·임베딩·벡터DB 선택 화면 |
| KB 테스트 | KB → Test knowledge base | 질문 입력 → 검색 결과 청크 + 소스 확인 |
| Sync 이력 | KB → Data sources → Sync history | 마지막 동기화 시간, 처리 문서 수 |
| OpenSearch | OpenSearch Service → Serverless | 컬렉션, 인덱스 이름, 벡터 차원 수 |
| 비용 확인 | Cost Explorer → OpenSearch Serverless | AOSS OCU(Compute Unit) 비용 |

> **포인트 1**: KB Test 탭에서 질문을 입력하면 검색된 청크(passage)와 출처 S3 경로를 직접 확인할 수 있습니다. retrieve API와 동일한 결과입니다.

> **포인트 2**: OpenSearch Serverless 콘솔에서 인덱스 매핑을 보면 `bedrock-knowledge-base-default-index` 이름의 벡터 인덱스와 임베딩 차원 수(텍스트=1024, 멀티모달=3072)를 확인할 수 있습니다.

---

## 파일별 핵심 내용 및 연관성

```
P3_01_rag_setup.py
  └─ AWS 계정/리전/IAM 권한 사전 점검
  └─ 임베딩 모델 접근 가능 여부 확인
  └─ 이후 모든 P3 파일의 전제조건

P3_02_rag_s3.py
  └─ S3 버킷 2개 생성 (데이터 버킷 + MM output 버킷)
  └─ text/ 프리픽스에 텍스트 PDF 업로드
  └─ multimodal/ 프리픽스에 멀티모달 PDF 업로드
  └─ Console S3 확인 URL 자동 출력

P3_03_rag_kb_create.py            ← 핵심 (콘솔 필수)
  └─ Console에서 KB 2개 생성 후 이 파일로 상태 확인 + Sync 시작
  └─ rag_config.json 에 KB ID 저장 → 이후 모든 파일이 이 파일 참조
  └─ --wait 옵션: CREATING 상태 자동 대기
  └─ KB 생성을 Console에서 해야 하는 이유:
       iam:CreateRole + aoss:CreateCollection 권한은 콘솔이 자동 처리

P3_04_rag_kb_test.py
  └─ Console KB Test 탭 사용법 안내 출력
  └─ Python retrieve API로 동일 결과 자동 검증
  └─ retrieve vs retrieve_and_generate 차이 비교

P3_05_rag_retrieve.py             ← 핵심 (API 실습)
  └─ retrieve: 청크 검색만 (LLM 호출 없음)
  └─ retrieve_and_generate: 검색 + LLM 답변 생성 통합
  └─ 텍스트 KB vs 멀티모달 KB 동일 질문 응답 비교
  └─ numberOfResults, searchType(HYBRID/SEMANTIC) 파라미터 실습

P3_06_rag_opensearch.py
  └─ AOSS 컬렉션 ARN → OpenSearch 엔드포인트 조회
  └─ 벡터 인덱스 매핑 확인 (차원 수, 필드명)
  └─ 저장된 벡터 문서 수 카운트
  └─ AOSS 권한 없으면 Console 가이드 출력

P3_06_rag_opensearch_dashboard.py
  └─ OpenSearch Dashboards 접속 가이드
  └─ Dev Tools에서 직접 쿼리하는 방법

P3_07_rag_chatbot.py              ← 핵심 (통합 UI)
  └─ 텍스트 KB / 멀티모달 KB 탭 전환 챗봇
  └─ 검색 청크 소스(S3 경로, 페이지 번호) 사이드바 표시
  └─ retrieve_and_generate 스트리밍 응답

P3_07_rag_file_chatbot.py
  └─ 파일 업로드 + 즉시 RAG 질의 (KB 없이)
  └─ InlineDocumentSource를 이용한 임시 컨텍스트 검색

P3_08_rag_managed_kb.py
  └─ 전체 리소스 상태 요약 (KB, S3)
  └─ --delete-kb / --delete-s3 / --delete-all 옵션으로 정리
  └─ 실습 완료 후 AOSS OCU 비용 방지를 위해 반드시 실행

P3_08_rag_managed_dashboard.py
  └─ 리소스 상태를 콘솔 URL과 함께 시각적으로 출력
```

---

## 코드에서 중요한 부분

### 1. retrieve vs retrieve_and_generate — 언제 무엇을 쓸까
```python
# retrieve: 청크만 반환 (LLM 호출 없음, 빠름, 저렴)
resp = agent_runtime.retrieve(
    knowledgeBaseId=KB_ID,
    retrievalQuery={"text": "5G 무제한 요금제 가격은?"},
    retrievalConfiguration={
        "vectorSearchConfiguration": {"numberOfResults": 5}
    },
)
chunks = resp["retrievalResults"]  # 검색된 텍스트 청크 리스트

# retrieve_and_generate: 검색 + LLM 답변 (편리하지만 비용 발생)
resp = agent_runtime.retrieve_and_generate(
    input={"text": "5G 무제한 요금제 가격은?"},
    retrieveAndGenerateConfiguration={
        "type": "KNOWLEDGE_BASE",
        "knowledgeBaseConfiguration": {
            "knowledgeBaseId": KB_ID,
            "modelArn": GEN_MODEL_ARN,
        },
    },
)
answer = resp["output"]["text"]
```

### 2. rag_config.json — 파일 간 KB ID 공유 방법
```python
# P3_03에서 저장
cfg = {"text_kb_id": "ABCDE12345", "multimodal_kb_id": "FGHIJ67890", ...}
Path("rag_config.json").write_text(json.dumps(cfg))

# P3_04 이후 모든 파일에서 로드
cfg = json.loads(Path("rag_config.json").read_text())
text_kb_id = cfg["text_kb_id"]
```

### 3. 텍스트 KB vs 멀티모달 KB 핵심 차이
```python
# 텍스트 KB
# - 파서: Default (텍스트 추출)
# - 임베딩: Titan Text Embeddings V2 (1024차원)
# - 적합: 표, 수치 데이터가 많은 문서

# 멀티모달 KB
# - 파서: Bedrock Data Automation (BDA) + Claude (이미지/표 이해)
# - 임베딩: Nova Multimodal Embeddings (3072차원)
# - 적합: 그래프, 다이어그램, 이미지가 포함된 문서
```

### 4. Hybrid Search — 키워드 + 시맨틱 동시 검색
```python
retrievalConfiguration={
    "vectorSearchConfiguration": {
        "numberOfResults": 5,
        "overrideSearchType": "HYBRID",  # SEMANTIC(기본) vs HYBRID
    }
}
# HYBRID: 벡터 유사도 + 키워드 BM25 결합 → 정확한 고유명사 포함 검색에 유리
```

### 5. InvokeModelWithResponseStream — retrieve_and_generate 스트리밍 대안
```python
# retrieve_and_generate는 스트리밍 미지원
# → retrieve로 청크 가져온 뒤 converse_stream으로 LLM 스트리밍 직접 구성
chunks = retrieve(question)
context = "\n".join([c["content"]["text"] for c in chunks])
stream  = bedrock.converse_stream(
    modelId=MODEL_ID,
    messages=[{"role": "user", "content": [{"text": f"컨텍스트:\n{context}\n\n질문: {question}"}]}],
    ...
)
```

---

## KB 생성 시 콘솔 선택 항목 요약

### 텍스트 KB (`telco-rateplan-text-kb`)
| 항목 | 선택값 |
|------|--------|
| 데이터 소스 | S3: `s3://telco-rateplan-kb-*/text/` |
| 파서 | Default parser |
| 임베딩 모델 | Titan Text Embeddings V2 (`amazon.titan-embed-text-v2:0`) |
| 벡터 DB | OpenSearch Serverless — Quick create |

### 멀티모달 KB (`telco-rateplan-multimodal-kb`)
| 항목 | 선택값 |
|------|--------|
| 데이터 소스 | S3: `s3://telco-rateplan-kb-*/multimodal/` |
| 파서 | Bedrock Data Automation (BDA) |
| MM output 버킷 | `s3://telco-rateplan-kb-mm-output-*/` |
| 임베딩 모델 | Nova Multimodal Embeddings (`amazon.nova-2-multimodal-embeddings-v1:0`) |
| 벡터 DB | OpenSearch Serverless — Quick create |

---

## AWS만의 장점

| 장점 | 설명 |
|------|------|
| **완전 관리형 파이프라인** | 문서 청킹 → 임베딩 → 벡터 저장 → 검색을 AWS가 자동 관리 |
| **멀티모달 파싱** | BDA + Claude로 이미지·표·그래프를 텍스트로 이해해 인덱싱 |
| **Hybrid Search** | 벡터 유사도 + BM25 키워드 검색 자동 결합 — 별도 구현 불필요 |
| **Guardrails 연계** | retrieve_and_generate 응답에 Guardrails 적용 가능 |
| **Grounding 검사** | 응답이 소스 문서에 근거하는지 자동 점수 산출 (환각 억제) |
| **소스 인용** | 응답에 S3 경로, 페이지 번호, 점수 자동 포함 — 출처 추적 가능 |
| **자동 Sync** | S3 문서 변경 시 증분 동기화 — 전체 재인덱싱 불필요 |

---

## 실행 순서

```bash
# 1. 사전 준비
python3 P3_01_rag_setup.py          # 권한 점검
python3 P3_02_rag_s3.py             # S3 버킷 + PDF 업로드

# 2. KB 생성 (콘솔 필수)
#    → AWS 콘솔에서 텍스트 KB, 멀티모달 KB 각각 생성
#    → KB ID 메모 후 아래 실행

python3 P3_03_rag_kb_create.py --wait   # KB 상태 확인 + Sync + rag_config.json 저장

# 3. 검증
python3 P3_04_rag_kb_test.py        # KB 테스트 (retrieve)
python3 P3_05_rag_retrieve.py       # retrieve / retrieve_and_generate 비교
python3 P3_06_rag_opensearch.py     # 벡터 인덱스 확인

# 4. 챗봇
streamlit run P3_07_rag_chatbot.py \
  --server.port 8503 --server.headless true

# 5. 정리 (AOSS OCU 비용 방지)
python3 P3_08_rag_managed_kb.py --delete-all
```

---

## 비용 주의사항

> AOSS(OpenSearch Serverless)는 **사용하지 않아도 OCU 비용이 발생**합니다.
> 실습 완료 후 반드시 `P3_08_rag_managed_kb.py --delete-all` 을 실행하세요.

| 서비스 | 과금 방식 |
|--------|----------|
| OpenSearch Serverless | OCU 단위 시간당 과금 (컬렉션 존재만으로 발생) |
| Titan/Nova 임베딩 | 토큰당 과금 (Sync 시 1회 발생) |
| S3 | 저장 용량 + 요청 수 (교육용 수준은 미미) |
| retrieve_and_generate | LLM 호출 토큰 비용 |
