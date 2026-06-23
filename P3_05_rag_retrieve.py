"""
P3_05_rag_retrieve.py
────────────────────────────────────────────────────────────────────
RAG 챕터 05 — boto3 API 질의와 비교

자동 처리:  rag_config.json 에서 KB ID 자동 로드, 전체 비교 자동 실행
사용자 필요: 없음

실행:
  python3 P3_05_rag_retrieve.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import json
import sys
from pathlib import Path

REGION  = "us-east-1"
SEP     = "─" * 60
CONSOLE = f"https://{REGION}.console.aws.amazon.com"

CONFIG_FILE   = Path(__file__).parent / "rag_config.json"
GEN_MODEL_ID  = "us.anthropic.claude-sonnet-4-6"
ACCOUNT_ID    = boto3.client("sts").get_caller_identity()["Account"]
GEN_MODEL_ARN = f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:inference-profile/{GEN_MODEL_ID}"

agent_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)


def load_kb_ids() -> tuple[str, str]:
    if not CONFIG_FILE.exists():
        print(f"  ❌ 설정 파일 없음. P3_03_rag_kb_create.py 를 먼저 실행하세요.")
        sys.exit(1)
    cfg  = json.loads(CONFIG_FILE.read_text())
    t_id = cfg.get("text_kb_id", "")
    m_id = cfg.get("multimodal_kb_id", "")
    if not t_id or not m_id:
        print(f"  ❌ KB ID 없음. P3_03_rag_kb_create.py 를 다시 실행하세요.")
        sys.exit(1)
    print(f"  ✅ KB ID 로드: TEXT={t_id}  MULTIMODAL={m_id}")
    return t_id, m_id


# ── 핵심 함수 1: retrieve ─────────────────────────────────────
def retrieve_chunks(kb_id: str, query: str, top_k: int = 3) -> list:
    """벡터 검색만 수행 (LLM 생성 없음). RAG 파이프라인의 R 단계."""
    resp = agent_runtime.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": top_k}
        },
    )
    return [
        {
            "score": round(r.get("score", 0.0), 4),
            "text":  r["content"]["text"],
            "uri":   r.get("location", {}).get("s3Location", {}).get("uri", ""),
        }
        for r in resp["retrievalResults"]
    ]


# ── 핵심 함수 2: retrieve_and_generate ───────────────────────
def ask(kb_id: str, query: str) -> tuple[str, list]:
    """검색 + LLM 생성. RAG 파이프라인의 R+G 단계."""
    resp = agent_runtime.retrieve_and_generate(
        input={"text": query},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb_id,
                "modelArn":        GEN_MODEL_ARN,
            },
        },
    )
    return resp["output"]["text"], resp.get("citations", [])


# ════════════════════════════════════════════════════════════════
# 실행
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(" P3_05_rag_retrieve.py")
    print(" RAG 실습 05 — boto3 API 질의와 비교")
    print("=" * 60)

    TEXT_KB_ID, MULTIMODAL_KB_ID = load_kb_ids()

    # ── STEP 1: retrieve 단독 ────────────────────────────────────
    print(f"\n{SEP}")
    print("【STEP 1】 retrieve() — 벡터 검색 전용")
    print(SEP)
    print("  bedrock-agent-runtime.retrieve()")
    print("  반환: retrievalResults[] → content.text / score / location\n")
    QUERY = "5GX 요금제 월 요금이 얼마인가요?"
    print(f"  질문: {QUERY}\n")
    try:
        chunks = retrieve_chunks(TEXT_KB_ID, QUERY, top_k=3)
        for i, c in enumerate(chunks, 1):
            print(f"  [{i}] score={c['score']}")
            print(f"       {c['text'][:200]}...")
            if c["uri"]:
                print(f"       출처: {c['uri']}")
    except Exception as e:
        print(f"  ❌ {e}")

    # ── STEP 2: retrieve_and_generate ──────────────────────────
    print(f"\n{SEP}")
    print("【STEP 2】 retrieve_and_generate() — 검색 + LLM 생성")
    print(SEP)
    print(f"  모델 ARN: {GEN_MODEL_ARN}")
    print(f"  반환: output.text + citations[]\n")
    try:
        answer, citations = ask(TEXT_KB_ID, QUERY)
        print(f"  질문: {QUERY}")
        print(f"  답변: {answer[:400]}")
        print(f"\n  citations({len(citations)}개):")
        for i, cit in enumerate(citations[:3], 1):
            for ref in cit.get("retrievedReferences", [])[:1]:
                uri  = ref.get("location", {}).get("s3Location", {}).get("uri", "")
                text = ref.get("content", {}).get("text", "")[:100]
                print(f"  [{i}] {uri}")
                print(f"       {text}...")
    except Exception as e:
        print(f"  ❌ {e}")

    # ── STEP 3: 여러 질문 순서대로 ──────────────────────────────
    print(f"\n{SEP}")
    print("【STEP 3】 다양한 질문 테스트")
    print(SEP)
    questions = [
        "가장 저렴한 요금제는 무엇인가요?",
        "데이터 무제한 요금제를 추천해 주세요.",
        "약정 없이 사용 가능한 요금제가 있나요?",
    ]
    for q in questions:
        print(f"\n  질문: {q}")
        try:
            answer, citations = ask(TEXT_KB_ID, q)
            print(f"  답변: {answer[:250]}")
            print(f"  인용: {len(citations)}개")
        except Exception as e:
            print(f"  ❌ {e}")

    # ── STEP 4: 두 KB 비교 ──────────────────────────────────────
    print(f"\n{SEP}")
    print("【STEP 4】 텍스트 KB vs 멀티모달 KB 비교")
    print(SEP)
    print("  동일 질문에 대해 두 KB의 답변 품질 차이 확인\n")

    compare_questions = [
        "5GX 요금제 월 요금과 데이터 용량을 표로 설명해 주세요.",
        "가장 비싼 요금제와 가장 싼 요금제 차이는?",
    ]
    for q in compare_questions:
        print(f"  ══ 질문: {q}")
        for label, kb_id in [
            ("텍스트 KB   (Default parser  + Titan V2)",  TEXT_KB_ID),
            ("멀티모달 KB (BDA parser + Nova Embeddings)", MULTIMODAL_KB_ID),
        ]:
            print(f"\n  [{label}]")
            try:
                answer, citations = ask(kb_id, q)
                print(f"  {answer[:300]}")
                print(f"  인용: {len(citations)}개")
            except Exception as e:
                print(f"  ❌ {e}")
        print()

    print(f"  💡 멀티모달 KB:")
    print(f"     BDA(Bedrock Data Automation)가 PDF 표/이미지를 구조화 텍스트로 변환")
    print(f"     → 표 형태 요금 데이터 검색 정확도 향상")

    # ── STEP 5: API 구조 비교 ────────────────────────────────────
    print(f"\n{SEP}")
    print("【STEP 5】 API 구조 비교 정리")
    print(SEP)
    print("""
  ┌──────────────────────────┬──────────────────────────────────┐
  │ retrieve()               │ retrieve_and_generate()          │
  ├──────────────────────────┼──────────────────────────────────┤
  │ 검색 청크만 반환          │ 검색 + LLM 생성 답변 반환        │
  │ retrievalResults[]       │ output.text + citations[]        │
  │ 직접 LLM 프롬프트 구성 시│ 단순 QA, 챗봇                    │
  │ bedrock-agent-runtime    │ bedrock-agent-runtime            │
  └──────────────────────────┴──────────────────────────────────┘

  boto3 클라이언트 구분:
  bedrock-agent         → KB 관리 (create/delete/list)
  bedrock-agent-runtime → KB 질의 (retrieve/retrieve_and_generate)
""")

    print(f"\n{SEP}")
    print("【AWS Console 확인】")
    print(SEP)
    print(f"  텍스트 KB   : {CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases/{TEXT_KB_ID}")
    print(f"  멀티모달 KB : {CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases/{MULTIMODAL_KB_ID}")

    print(f"\n{'=' * 60}")
    print("  ✅ 완료 → 다음: python3 P3_06_rag_opensearch.py")
    print("=" * 60)
