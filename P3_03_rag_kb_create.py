"""
P3_03_rag_kb_create.py
────────────────────────────────────────────────────────────────────
RAG 챕터 03 — KB 생성 확인 + Sync 자동화

자동 처리:  KB 상태 확인, Sync 시작/대기, KB ID를 rag_config.json 저장
사용자 필요: Console에서 KB 2개 생성 (아래 STEP 0 가이드)

KB 생성이 Console에서만 가능한 이유:
  - iam:CreateRole 권한 없음 (서비스 역할 자동 생성 불가)
  - aoss:CreateCollection 권한 없음 (OpenSearch 컬렉션 자동 생성 불가)
  이 두 작업은 Console KB 생성 시 자동 처리됩니다.

실행:
  python3 P3_03_rag_kb_create.py          # KB 확인 + Sync + 설정 저장
  python3 P3_03_rag_kb_create.py --wait   # CREATING 대기
────────────────────────────────────────────────────────────────────
"""

import argparse
import boto3
import json
import time
from pathlib import Path

REGION    = "us-east-1"
SEP       = "─" * 60
CONSOLE   = f"https://{REGION}.console.aws.amazon.com"

TEXT_KB_NAME      = "telco-rateplan-text-kb"
MULTIMODAL_KB_NAME = "telco-rateplan-multimodal-kb"

# KB ID가 저장되는 공유 설정 파일 (10~13 파일이 자동으로 읽음)
CONFIG_FILE = Path(__file__).parent / "rag_config.json"

agent = boto3.client("bedrock-agent", region_name=REGION)
sts   = boto3.client("sts",           region_name=REGION)


# ── 설정 파일 로드/저장 ─────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}

def save_config(data: dict):
    existing = load_config()
    existing.update(data)
    CONFIG_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    print(f"  💾 설정 저장: {CONFIG_FILE}")


# ── KB 목록 ────────────────────────────────────────────────────
def list_all_kbs() -> list:
    try:
        return agent.list_knowledge_bases(maxResults=20).get("knowledgeBaseSummaries", [])
    except Exception as e:
        print(f"  KB 목록 오류: {e}")
        return []

def get_kb_by_name(name: str) -> dict | None:
    for kb in list_all_kbs():
        if kb["name"] == name:
            return kb
    return None


# ── KB 상세 ────────────────────────────────────────────────────
def describe_kb(kb_id: str) -> dict:
    try:
        return agent.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]
    except Exception:
        return {}


# ── Sync 실행 ─────────────────────────────────────────────────
def sync_kb(kb_id: str, kb_name: str):
    """데이터소스 Sync 시작 + 완료 대기."""
    try:
        ds_list = agent.list_data_sources(knowledgeBaseId=kb_id)
        sources = ds_list.get("dataSourceSummaries", [])
        if not sources:
            print(f"  ⚠️  [{kb_name}] 데이터소스 없음 — Console에서 KB 생성을 완료했는지 확인")
            return False

        for ds in sources:
            ds_id = ds["dataSourceId"]
            print(f"  Sync 시작: {ds['name']} ...", end="", flush=True)
            try:
                job = agent.start_ingestion_job(
                    knowledgeBaseId=kb_id,
                    dataSourceId=ds_id,
                )
                job_id = job["ingestionJob"]["ingestionJobId"]
            except agent.exceptions.ConflictException:
                print(" (이미 진행 중)")
                job_id = None

            if job_id:
                # 완료 대기 (최대 10분)
                for _ in range(120):
                    j      = agent.get_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id)
                    status = j["ingestionJob"]["status"]
                    if status == "COMPLETE":
                        stats   = j["ingestionJob"].get("statistics", {})
                        indexed = stats.get("numberOfNewDocumentsIndexed", 0)
                        scanned = stats.get("numberOfDocumentsScanned", 0)
                        print(f" ✅ COMPLETE (scanned={scanned}, indexed={indexed})")
                        return True
                    if status in ("FAILED", "STOPPED"):
                        print(f" ❌ {status}")
                        return False
                    print(".", end="", flush=True)
                    time.sleep(5)
                print(" ⏰ 타임아웃")
        return True
    except Exception as e:
        print(f"  Sync 오류: {e}")
        return False


# ── KB ACTIVE 대기 ────────────────────────────────────────────
def wait_active(kb_name: str, timeout: int = 300):
    print(f"  [{kb_name}] ACTIVE 대기...", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        kb = get_kb_by_name(kb_name)
        if not kb:
            print(" 없음")
            return False
        if kb["status"] == "ACTIVE":
            print(" ✅ ACTIVE")
            return True
        print(".", end="", flush=True)
        time.sleep(10)
    print(f" ⏰ 타임아웃")
    return False


# ── KB 상세 출력 ──────────────────────────────────────────────
def print_kb_info(kb: dict):
    kb_id  = kb["knowledgeBaseId"]
    status = kb["status"]
    mark   = "✅" if status == "ACTIVE" else "⏳"
    print(f"\n  {mark} {kb['name']} [{status}]")
    print(f"     KB ID   : {kb_id}")

    detail = describe_kb(kb_id)
    if detail:
        arn = detail.get("knowledgeBaseArn", "")
        print(f"     ARN     : {arn}")
        sc = detail.get("storageConfiguration", {})
        oss = sc.get("opensearchServerlessConfiguration", {})
        if oss:
            col_arn = oss.get("collectionArn", "")
            col_name = col_arn.split("/")[-1] if col_arn else ""
            print(f"     OSS ARN : {col_arn}")
            if col_name:
                print(f"     OSS 콘솔: {CONSOLE}/aos/home?region={REGION}#/collections")
        kbc = detail.get("knowledgeBaseConfiguration", {})
        vkbc = kbc.get("vectorKnowledgeBaseConfiguration", {})
        if vkbc:
            emb = vkbc.get("embeddingModelArn", "").split("/")[-1]
            print(f"     임베딩  : {emb}")
    print(f"     콘솔    : {CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases/{kb_id}")

    # 데이터소스 + Sync 상태
    try:
        for ds in agent.list_data_sources(knowledgeBaseId=kb_id).get("dataSourceSummaries", []):
            ds_id = ds["dataSourceId"]
            jobs  = agent.list_ingestion_jobs(knowledgeBaseId=kb_id, dataSourceId=ds_id).get("ingestionJobSummaries", [])
            if jobs:
                j      = jobs[0]
                jmark  = "✅" if j["status"] == "COMPLETE" else ("⏳" if j["status"] in ("STARTING","IN_PROGRESS") else "⚠️")
                stats  = j.get("statistics", {})
                indexed = stats.get("numberOfNewDocumentsIndexed", 0)
                print(f"     Sync    : {jmark} [{j['status']}] indexed={indexed}")
            else:
                print(f"     Sync    : 미실행")
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════
# 실행
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true", help="CREATING 상태 대기")
    args = parser.parse_args()

    print("=" * 60)
    print(" P3_03_rag_kb_create.py")
    print(" RAG 실습 03 — KB 생성 확인 + Sync 자동화")
    print("=" * 60)

    all_kbs   = list_all_kbs()
    kb_names  = {kb["name"] for kb in all_kbs}
    missing   = [n for n in [TEXT_KB_NAME, MULTIMODAL_KB_NAME] if n not in kb_names]

    # ── STEP 0: Console 가이드 (미생성인 KB가 있을 때) ─────────
    if missing:
        account = sts.get_caller_identity()["Account"]
        suffix  = account[-4:]
        data_bucket = f"telco-rateplan-kb-2026-{suffix}"
        mm_bucket   = f"telco-rateplan-kb-mm-output-2026-{suffix}"

        print(f"\n{SEP}")
        print("【★ 사용자 직접 수행 필요 ★】 Console에서 KB 생성")
        print(SEP)
        print(f"\n  미생성 KB: {missing}")
        print(f"\n  아래 이유로 자동 생성 불가 (SageMaker 역할 권한 제한):")
        print(f"    - iam:CreateRole   없음 → KB 서비스 역할 자동 생성 불가")
        print(f"    - aoss:CreateCollection 없음 → OpenSearch 컬렉션 자동 생성 불가")
        print(f"    Console KB 생성 마법사가 이 두 작업을 자동 처리합니다.")
        print(f"""
  Console 접속: {CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases

  ━━━ A. telco-rateplan-text-kb ━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Create knowledge base → Unstructured Vector Store KB
  2. 이름: telco-rateplan-text-kb
     IAM : Create and use a new service role  (자동 처리됨)
  3. 데이터소스 이름: text-pdf-source
     S3 URI: s3://{data_bucket}/text/
     파서  : Default parser
     청킹  : Default chunking
  4. 임베딩: Titan Text Embeddings V2
     벡터DB: Quick create → Amazon OpenSearch Serverless
  5. Create Knowledge Base → 생성 완료 대기 (~2분)
  6. Data source 탭 → text-pdf-source → Sync  클릭

  ━━━ B. telco-rateplan-multimodal-kb ━━━━━━━━━━━━━━━━━━━━━━
  1. Create knowledge base → Unstructured Vector Store KB
  2. 이름: telco-rateplan-multimodal-kb
     IAM : Create and use a new service role
  3. 데이터소스 이름: multimodal-pdf-source
     S3 URI: s3://{data_bucket}/multimodal/
     파서  : Amazon Bedrock Data Automation
       Use foundation models → Claude Sonnet 4.6 선택
     MM output bucket: {mm_bucket}
  4. 임베딩: Amazon Nova Multimodal Embeddings
             Embedding dimensions: 3072
     벡터DB: Quick create → Amazon OpenSearch Serverless
  5. Create Knowledge Base → 생성 완료 대기 (~2분)
  6. Data source 탭 → multimodal-pdf-source → Sync 클릭

  생성 완료 후 이 스크립트를 다시 실행하세요.
  python3 P3_03_rag_kb_create.py
""")

        if args.wait and missing:
            print(f"\n  --wait 모드: KB 생성 완료 대기 중 (Ctrl+C로 중단 가능)...")
            for name in missing:
                wait_active(name, timeout=600)
            all_kbs  = list_all_kbs()
            kb_names = {kb["name"] for kb in all_kbs}
            missing  = [n for n in [TEXT_KB_NAME, MULTIMODAL_KB_NAME] if n not in kb_names]

        if missing:
            print(f"\n  KB 생성 후 재실행하세요.")
            exit(0)

    # ── STEP 1: KB 상태 출력 ────────────────────────────────────
    print(f"\n{SEP}")
    print(f"【STEP 1】 Knowledge Base 목록 (총 {len(all_kbs)}개)")
    print(SEP)
    for kb in all_kbs:
        print_kb_info(kb)

    # ── STEP 2: ACTIVE 대기 (필요시) ────────────────────────────
    if args.wait:
        print(f"\n{SEP}")
        print("【STEP 2】 ACTIVE 상태 대기")
        print(SEP)
        for name in [TEXT_KB_NAME, MULTIMODAL_KB_NAME]:
            kb = get_kb_by_name(name)
            if kb and kb["status"] != "ACTIVE":
                wait_active(name)

    # ── STEP 3: Sync 실행 (ACTIVE KB만) ─────────────────────────
    print(f"\n{SEP}")
    print("【STEP 3】 자동 Sync 실행")
    print(SEP)
    print("  S3 PDF → OpenSearch 벡터 인덱스 동기화\n")
    for name in [TEXT_KB_NAME, MULTIMODAL_KB_NAME]:
        kb = get_kb_by_name(name)
        if kb and kb["status"] == "ACTIVE":
            print(f"  [{name}]")
            sync_kb(kb["knowledgeBaseId"], name)
        elif kb:
            print(f"  [{name}] 상태: {kb['status']} — Sync 건너뜁니다.")
        else:
            print(f"  [{name}] 없음")

    # ── STEP 4: KB ID 자동 저장 ─────────────────────────────────
    print(f"\n{SEP}")
    print("【STEP 4】 KB ID 자동 저장 (이후 파일에서 자동 로드)")
    print(SEP)
    config_data = {}
    for name, key in [(TEXT_KB_NAME, "text_kb_id"), (MULTIMODAL_KB_NAME, "multimodal_kb_id")]:
        kb = get_kb_by_name(name)
        if kb:
            config_data[key] = kb["knowledgeBaseId"]
            print(f"  {key}: {kb['knowledgeBaseId']}")

    if config_data:
        save_config(config_data)
        print(f"\n  ✅ 저장 완료: {CONFIG_FILE}")
        print(f"  → bedrock_10~13 파일이 자동으로 이 설정을 읽습니다.")
        print(f"  → KB ID를 직접 입력할 필요 없습니다.")
    else:
        print(f"  KB가 없어 저장할 내용이 없습니다.")

    # ── Console 확인 URL ─────────────────────────────────────────
    print(f"\n{SEP}")
    print("【AWS Console 확인】")
    print(SEP)
    print(f"  Knowledge Bases : {CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases")
    print(f"  OpenSearch 컬렉션: {CONSOLE}/aos/home?region={REGION}#/collections")

    print(f"\n{'=' * 60}")
    if config_data:
        print("  ✅ 완료 → 다음: python3 P3_04_rag_kb_test.py")
    else:
        print("  Console에서 KB 생성 후 재실행하세요.")
    print("=" * 60)
