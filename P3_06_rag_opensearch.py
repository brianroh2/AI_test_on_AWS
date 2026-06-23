"""
P3_06_rag_opensearch.py
────────────────────────────────────────────────────────────────────
RAG 챕터 06 — OpenSearch Serverless 벡터 인덱스 확인

자동 처리:  rag_config.json KB ID 로드, 컬렉션 ARN 조회, 인덱스 매핑/카운트
사용자 필요: 없음 (09 완료 후 바로 실행)

실행:
  python3 P3_06_rag_opensearch.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import json
import sys
import requests
from pathlib import Path
from requests_aws4auth import AWS4Auth

REGION  = "us-east-1"
SEP     = "─" * 60
CONSOLE = f"https://{REGION}.console.aws.amazon.com"

CONFIG_FILE = Path(__file__).parent / "rag_config.json"

agent = boto3.client("bedrock-agent",        region_name=REGION)
aoss  = boto3.client("opensearchserverless", region_name=REGION)


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


def get_awsauth():
    sess = boto3.Session(region_name=REGION)
    cred = sess.get_credentials().get_frozen_credentials()
    return AWS4Auth(cred.access_key, cred.secret_key, REGION, "aoss",
                    session_token=cred.token)


# ── KB → AOSS 컬렉션 정보 추출 ───────────────────────────────
def get_collection_info(kb_id: str) -> dict:
    try:
        kb  = agent.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]
        sc  = kb.get("storageConfiguration", {})
        oss = sc.get("opensearchServerlessConfiguration", {})
        return {
            "collectionArn": oss.get("collectionArn", ""),
            "indexName":     oss.get("vectorIndexName", ""),
            "fieldMapping":  oss.get("fieldMapping", {}),
        }
    except Exception as e:
        print(f"  KB 조회 오류: {e}")
        return {}


# ── AOSS 컬렉션 엔드포인트 가져오기 ──────────────────────────
# SageMaker 실행 역할에 aoss:BatchGetCollection 권한이 없으므로
# ARN의 collection-id로 엔드포인트 URL을 직접 계산
def get_endpoint(col_arn: str) -> str:
    col_id = col_arn.split("/")[-1]
    endpoint = f"https://{col_id}.{REGION}.aoss.amazonaws.com"
    print(f"  컬렉션 ID  : {col_id}")
    print(f"  엔드포인트 : {endpoint}")
    print(f"  콘솔 URL   : {CONSOLE}/aos/home?region={REGION}#/collections")
    return endpoint


AOSS_403_GUIDE = """
  ⚠️  HTTP 403 — AOSS 데이터 접근 정책 미등록
  ─────────────────────────────────────────────────────
  원인: SageMaker 실행 역할이 OpenSearch Serverless 컬렉션의
        데이터 접근 정책(Data Access Policy)에 포함되지 않음.
        (Bedrock KB 서비스 역할만 접근 가능한 상태)

  【Console에서 직접 확인하는 방법 (권장)】
  1. https://us-east-1.console.aws.amazon.com/aos/home?region=us-east-1#/collections
  2. 컬렉션 클릭 → 상단 [Indexes] 탭
  3. bedrock-knowledge-base-default-index 클릭
  4. [Mappings] 탭 → bedrock-knowledge-base-default-vector 필드 확인
     (type: knn_vector, dimension: 1024 또는 3072)
  5. [Documents] 탭 → 인덱싱된 청크 수 확인

  【boto3로 접근하려면 (선택)】
  AOSS Console → 해당 컬렉션 → [Data access] 탭
  → 기존 정책 편집 → Principals에 아래 ARN 추가:
    arn:aws:iam::560631060082:role/AmazonSageMaker-ExecutionRole-20260622T130537
  ─────────────────────────────────────────────────────"""


_403_shown = False  # 한 컬렉션당 가이드 중복 출력 방지


def _check_403(resp, step_name: str) -> bool:
    """403이면 가이드 출력 후 True 반환 (caller가 skip할 수 있도록)"""
    global _403_shown
    if resp.status_code == 403:
        print(f"  {step_name} 조회 실패: HTTP 403")
        if not _403_shown:
            print(AOSS_403_GUIDE)
            _403_shown = True
        return True
    return False


# ── 인덱스 매핑 ──────────────────────────────────────────────
def get_index_mapping(endpoint: str, idx_name: str):
    if not endpoint:
        return
    awsauth = get_awsauth()
    try:
        resp = requests.get(f"{endpoint}/{idx_name}/_mapping",
                            auth=awsauth, timeout=10)
        if _check_403(resp, "매핑"):
            return
        if resp.status_code == 200:
            props = (resp.json().get(idx_name, {})
                     .get("mappings", {}).get("properties", {}))
            print(f"  인덱스 필드 수: {len(props)}")
            for fname, finfo in list(props.items())[:8]:
                ftype = finfo.get("type", "object")
                dims  = finfo.get("dimension", "")
                extra = f"  dim={dims}" if dims else ""
                print(f"    {fname}: {ftype}{extra}")
        else:
            print(f"  매핑 조회 실패: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  매핑 오류: {e}")


# ── 문서 수 ──────────────────────────────────────────────────
def get_doc_count(endpoint: str, idx_name: str) -> int:
    if not endpoint:
        return -1
    awsauth = get_awsauth()
    try:
        resp = requests.get(f"{endpoint}/{idx_name}/_count",
                            auth=awsauth, timeout=10)
        if resp.status_code == 403:
            return -2  # 403 구분 코드
        if resp.status_code == 200:
            return resp.json().get("count", 0)
    except Exception:
        pass
    return -1


# ── kNN 구조 확인 (zero vector) ───────────────────────────────
def knn_structure_check(endpoint: str, idx_name: str, vec_field: str, dim: int):
    if not endpoint:
        return
    awsauth = get_awsauth()
    body = {
        "size": 3,
        "query": {
            "knn": {
                vec_field: {"vector": [0.0] * dim, "k": 3}
            }
        },
        "_source": {"excludes": [vec_field]},
    }
    try:
        resp = requests.post(f"{endpoint}/{idx_name}/_search",
                             auth=awsauth,
                             json=body, timeout=15,
                             headers={"Content-Type": "application/json"})
        if _check_403(resp, "kNN 쿼리"):
            return
        if resp.status_code == 200:
            hits  = resp.json().get("hits", {}).get("hits", [])
            total = resp.json().get("hits", {}).get("total", {}).get("value", 0)
            print(f"  kNN 총 문서: {total}")
            for h in hits[:2]:
                src   = h.get("_source", {})
                text  = str(src.get("AMAZON_BEDROCK_TEXT_CHUNK",
                                    src.get("text", "")))[:120]
                score = round(h.get("_score", 0), 4)
                print(f"    score={score}  {text}...")
        else:
            print(f"  kNN 쿼리 실패: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  kNN 오류: {e}")


# ════════════════════════════════════════════════════════════════
# 실행
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(" P3_06_rag_opensearch.py")
    print(" RAG 실습 06 — OpenSearch Serverless 벡터 인덱스 확인")
    print("=" * 60)

    TEXT_KB_ID, MULTIMODAL_KB_ID = load_kb_ids()

    KB_LIST = [
        ("텍스트 KB   (Titan V2,  dim=1024)", TEXT_KB_ID,       1024),
        ("멀티모달 KB (Nova,      dim=3072)", MULTIMODAL_KB_ID, 3072),
    ]

    for label, kb_id, dim in KB_LIST:
        _403_shown = False
        print(f"\n{'═'*60}")
        print(f"  {label}")
        print(f"{'═'*60}")

        info = get_collection_info(kb_id)
        if not info or not info.get("collectionArn"):
            print(f"  컬렉션 ARN 없음")
            continue

        col_arn  = info["collectionArn"]
        idx_name = info["indexName"]
        vec_fld  = info["fieldMapping"].get("vectorField",
                   "bedrock-knowledge-base-default-vector")

        print(f"  컬렉션 ARN : {col_arn}")
        print(f"  인덱스 이름: {idx_name}")
        print(f"  벡터 필드  : {vec_fld}")
        print(f"  벡터 차원  : {dim}")

        # ── STEP 1: 컬렉션 메타데이터 + 엔드포인트 ───────────────
        print(f"\n  [STEP 1] 컬렉션 메타데이터")
        endpoint = get_endpoint(col_arn)

        if not endpoint:
            print(f"  ⚠️  엔드포인트 조회 실패")
            print(f"  Console에서 확인: {CONSOLE}/aos/home?region={REGION}#/collections")
            continue

        # ── STEP 2: 인덱스 필드 매핑 ─────────────────────────────
        print(f"\n  [STEP 2] 인덱스 필드 매핑 (knn_vector dim 확인)")
        get_index_mapping(endpoint, idx_name)

        # ── STEP 3: 문서 수 ──────────────────────────────────────
        count = get_doc_count(endpoint, idx_name)
        if count >= 0:
            print(f"\n  [STEP 3] 인덱싱된 청크 수: {count}")
        elif count == -2:
            print(f"\n  [STEP 3] 청크 수: HTTP 403 (위 가이드 참조)")
        else:
            print(f"\n  [STEP 3] 청크 수 조회 실패")

        # ── STEP 4: kNN 구조 확인 ─────────────────────────────────
        print(f"\n  [STEP 4] kNN 벡터 검색 구조 확인")
        knn_structure_check(endpoint, idx_name, vec_fld, dim)

    # ── Console 확인 가이드 ──────────────────────────────────────
    print(f"\n{SEP}")
    print("【AWS Console 확인 포인트】")
    print(SEP)
    print(f"""
  OpenSearch Serverless: {CONSOLE}/aos/home?region={REGION}#/collections
  ◎ Collections 탭 → 두 컬렉션 ACTIVE 확인
  ◎ 컬렉션 클릭 → Indices 탭 → bedrock-knowledge-base-... 인덱스 확인
  ◎ 인덱스명 클릭 → Mappings → knn_vector 타입 + dimension 확인

  Bedrock KB: {CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases
  ◎ 각 KB → Data source → Sync status: Completed 확인
""")

    print(f"{'=' * 60}")
    print("  ✅ 완료 → 다음: streamlit run P3_07_rag_chatbot.py --server.port 8503")
    print("=" * 60)
