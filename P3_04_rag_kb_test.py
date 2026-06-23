"""
P3_04_rag_kb_test.py
────────────────────────────────────────────────────────────────────
RAG 챕터 04 — KB 테스트 (Console 가이드 + Python 자동 쿼리)

자동 처리:  rag_config.json 에서 KB ID 자동 로드, 전체 쿼리 자동 실행
사용자 필요: 없음 (09 파일 완료 후 바로 실행)

실행:
  python3 P3_04_rag_kb_test.py
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


# ── 설정 로드 ─────────────────────────────────────────────────
def load_kb_ids() -> tuple[str, str]:
    if not CONFIG_FILE.exists():
        print(f"  ❌ 설정 파일 없음: {CONFIG_FILE}")
        print(f"     P3_03_rag_kb_create.py 를 먼저 실행하세요.")
        sys.exit(1)
    cfg = json.loads(CONFIG_FILE.read_text())
    text_id = cfg.get("text_kb_id", "")
    mm_id   = cfg.get("multimodal_kb_id", "")
    if not text_id or not mm_id:
        print(f"  ❌ KB ID 미저장. P3_03_rag_kb_create.py 를 다시 실행하세요.")
        sys.exit(1)
    print(f"  ✅ 설정 로드: {CONFIG_FILE}")
    print(f"     TEXT_KB_ID      = {text_id}")
    print(f"     MULTIMODAL_KB_ID = {mm_id}")
    return text_id, mm_id


# ── retrieve ─────────────────────────────────────────────────
def retrieve(kb_id: str, query: str, top_k: int = 3) -> list:
    resp = agent_runtime.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": top_k}},
    )
    return [
        {
            "score": round(r.get("score", 0.0), 4),
            "text":  r["content"]["text"],
            "uri":   r.get("location", {}).get("s3Location", {}).get("uri", ""),
        }
        for r in resp["retrievalResults"]
    ]


# ── retrieve_and_generate ─────────────────────────────────────
def ask(kb_id: str, query: str) -> tuple[str, int]:
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
    return resp["output"]["text"], len(resp.get("citations", []))


# ════════════════════════════════════════════════════════════════
# 실행
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(" P3_04_rag_kb_test.py")
    print(" RAG 실습 04 — KB 테스트")
    print("=" * 60)

    TEXT_KB_ID, MULTIMODAL_KB_ID = load_kb_ids()

    # ── STEP 0: Console Test KB 가이드 ──────────────────────────
    print(f"\n{SEP}")
    print("【STEP 0】 Console에서 직접 테스트 (선택)")
    print(SEP)
    print(f"""
  ① {CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases/{TEXT_KB_ID}
  ② 우측 'Test Knowledge Base' 클릭

  검색 전용 (Retrieval only):
    Generate responses 토글 OFF → 질문 입력 → 청크 목록 확인

  검색 + 생성 (Retrieval and response):
    Generate responses 토글 ON → Select model: Claude Sonnet 4.6
    → 질문 입력 → 답변 + citations 확인

  파라미터 조정 (Number of source chunks / Search type):
    기본: Semantic, chunks=5
""")

    # ── STEP 1: retrieve 검색 전용 ──────────────────────────────
    print(f"\n{SEP}")
    print("【STEP 1】 retrieve — 벡터 검색 결과 (검색 전용)")
    print(SEP)
    QUERY = "5GX 요금제 월 요금이 얼마인가요?"
    print(f"  질문: {QUERY}\n")
    try:
        chunks = retrieve(TEXT_KB_ID, QUERY, top_k=3)
        for i, c in enumerate(chunks, 1):
            print(f"  [{i}] score={c['score']}")
            print(f"       {c['text'][:180]}...")
            if c["uri"]:
                print(f"       출처: {c['uri']}")
        print(f"\n  💡 score 1에 가까울수록 질문과 유사한 청크")
    except Exception as e:
        print(f"  ❌ {e}")

    # ── STEP 2: retrieve_and_generate ──────────────────────────
    print(f"\n{SEP}")
    print("【STEP 2】 retrieve_and_generate — 검색 + 생성")
    print(SEP)
    questions = [
        "5GX 요금제 월 요금이 얼마인가요?",
        "데이터 무제한 요금제를 추천해 주세요.",
        "약정 없이 사용할 수 있는 요금제는?",
    ]
    for q in questions:
        print(f"\n  질문: {q}")
        try:
            answer, n_cite = ask(TEXT_KB_ID, q)
            print(f"  답변: {answer[:300]}")
            print(f"  인용: {n_cite}개")
        except Exception as e:
            print(f"  ❌ {e}")

    # ── STEP 3: 검색 파라미터 실험 ──────────────────────────────
    print(f"\n{SEP}")
    print("【STEP 3】 numberOfResults + searchType 파라미터 실험")
    print(SEP)
    QUERY2 = "5GX 요금제 특징은?"
    for n, st in [(2, "SEMANTIC"), (5, "SEMANTIC"), (5, "HYBRID")]:
        try:
            resp = agent_runtime.retrieve(
                knowledgeBaseId=TEXT_KB_ID,
                retrievalQuery={"text": QUERY2},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {
                        "numberOfResults": n,
                        "overrideSearchType": st,
                    }
                },
            )
            items  = resp["retrievalResults"]
            scores = [round(r.get("score", 0), 4) for r in items]
            print(f"  n={n}, type={st:8s} → {len(items)}건  scores={scores}")
        except Exception as e:
            print(f"  n={n}, type={st:8s} → 오류: {e}")

    # ── STEP 4: 두 KB 비교 ──────────────────────────────────────
    print(f"\n{SEP}")
    print("【STEP 4】 텍스트 KB vs 멀티모달 KB 비교")
    print(SEP)
    COMPARE_Q = "5GX 요금제 월 요금과 데이터 용량은?"
    print(f"  질문: {COMPARE_Q}\n")
    for label, kb_id in [
        ("텍스트 KB   (Titan Embeddings)", TEXT_KB_ID),
        ("멀티모달 KB (Nova Embeddings) ", MULTIMODAL_KB_ID),
    ]:
        print(f"  ── {label} ──")
        try:
            answer, n_cite = ask(kb_id, COMPARE_Q)
            print(f"  {answer[:300]}")
            print(f"  인용 {n_cite}개\n")
        except Exception as e:
            print(f"  ❌ {e}\n")

    # ── Console 확인 URL ─────────────────────────────────────────
    print(f"\n{SEP}")
    print("【AWS Console 확인】")
    print(SEP)
    print(f"  텍스트 KB   : {CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases/{TEXT_KB_ID}")
    print(f"  멀티모달 KB : {CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases/{MULTIMODAL_KB_ID}")

    print(f"\n{'=' * 60}")
    print("  ✅ 완료 → 다음: python3 P3_05_rag_retrieve.py")
    print("=" * 60)
