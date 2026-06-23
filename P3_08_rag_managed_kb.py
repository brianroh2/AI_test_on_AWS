"""
P3_08_rag_managed_kb.py
────────────────────────────────────────────────────────────────────
RAG 챕터 08 [옵션] — 리소스 정리 / 재생성 자동화

자동 처리:  rag_config.json 로드, KB/S3 상태 확인, KB 삭제 자동화
사용자 필요:
  - KB 재생성은 Console 필요 (iam:CreateRole / aoss:CreateCollection 권한 없음)
  - S3 버킷 삭제는 이 파일이 자동 처리

실행:
  python3 P3_08_rag_managed_kb.py            # 전체 리소스 상태 요약
  python3 P3_08_rag_managed_kb.py --delete-kb  # KB 삭제
  python3 P3_08_rag_managed_kb.py --delete-s3  # S3 버킷 + 파일 삭제
  python3 P3_08_rag_managed_kb.py --delete-all # KB + S3 모두 삭제
────────────────────────────────────────────────────────────────────
"""

import argparse
import boto3
import json
import sys
import time
from pathlib import Path

REGION  = "us-east-1"
SEP     = "─" * 60
CONSOLE = f"https://{REGION}.console.aws.amazon.com"

CONFIG_FILE = Path(__file__).parent / "rag_config.json"

agent = boto3.client("bedrock-agent", region_name=REGION)
s3    = boto3.client("s3",            region_name=REGION)
sts   = boto3.client("sts",           region_name=REGION)


# ── 설정 로드 ─────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}

def get_bucket_names() -> tuple[str, str]:
    account = sts.get_caller_identity()["Account"]
    suffix  = account[-4:]
    return (
        f"telco-rateplan-kb-2026-{suffix}",
        f"telco-rateplan-kb-mm-output-2026-{suffix}",
    )


# ════════════════════════════════════════════════════════════════
# 상태 요약
# ════════════════════════════════════════════════════════════════
def print_status():
    print(f"\n{SEP}")
    print("【현재 리소스 상태】")
    print(SEP)

    cfg          = load_config()
    data_bucket, mm_bucket = get_bucket_names()

    # KB 상태
    print(f"\n  [Bedrock Knowledge Bases]")
    try:
        kbs = agent.list_knowledge_bases(maxResults=20).get("knowledgeBaseSummaries", [])
        if kbs:
            for kb in kbs:
                mark = "✅" if kb["status"] == "ACTIVE" else "⏳"
                print(f"  {mark} {kb['name']:40s} [{kb['status']}]  ID: {kb['knowledgeBaseId']}")
                print(f"     콘솔: {CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases/{kb['knowledgeBaseId']}")
        else:
            print(f"  (없음)")
    except Exception as e:
        print(f"  오류: {e}")

    # S3 상태
    print(f"\n  [S3 버킷]")
    for bucket in [data_bucket, mm_bucket]:
        try:
            s3.head_bucket(Bucket=bucket)
            resp  = s3.list_objects_v2(Bucket=bucket)
            count = resp.get("KeyCount", 0)
            size  = sum(o["Size"] for o in resp.get("Contents", []))
            print(f"  ✅ {bucket}  ({count}개 파일, {size//1024}KB)")
            print(f"     콘솔: https://s3.console.aws.amazon.com/s3/buckets/{bucket}?region={REGION}")
        except Exception:
            print(f"  ❌ {bucket}  (없음)")

    # rag_config.json
    print(f"\n  [rag_config.json]")
    if cfg:
        for k, v in cfg.items():
            print(f"  {k}: {v}")
    else:
        print(f"  (없음 또는 비어있음)")

    # 자동/수동 구분 요약
    print(f"\n{SEP}")
    print("  자동화 가능 작업 vs 수동 필요 작업")
    print(SEP)
    print("""
  ┌─────────────────────────────┬────────────┬──────────────────────────┐
  │ 작업                         │ 자동화     │ 사유                      │
  ├─────────────────────────────┼────────────┼──────────────────────────┤
  │ S3 버킷 생성/삭제             │ ✅ 자동    │ s3 권한 있음              │
  │ S3 PDF 업로드                 │ ✅ 자동    │ s3 권한 있음              │
  │ KB 삭제                      │ ✅ 자동    │ bedrock:DeleteKB 있음     │
  │ KB Sync                      │ ✅ 자동    │ bedrock:StartIngestion    │
  │ KB 질의 (retrieve/r_and_g)   │ ✅ 자동    │ agent-runtime 권한 있음   │
  │ OpenSearch 벡터 확인          │ ✅ 자동    │ AOSS REST API 사용        │
  │ KB 생성 (신규)                │ ❌ Console │ iam:CreateRole 권한 없음  │
  │   - IAM 서비스 역할 생성      │ ❌ Console │ AOSS에 IAM 위임 불가      │
  │   - AOSS 컬렉션 생성          │ ❌ Console │ aoss:CreateCollection 없음│
  └─────────────────────────────┴────────────┴──────────────────────────┘
""")


# ════════════════════════════════════════════════════════════════
# KB 삭제
# ════════════════════════════════════════════════════════════════
def delete_kbs():
    print(f"\n{SEP}")
    print("【KB 삭제】")
    print(SEP)
    try:
        kbs = agent.list_knowledge_bases(maxResults=20).get("knowledgeBaseSummaries", [])
        target_names = {"telco-rateplan-text-kb", "telco-rateplan-multimodal-kb"}
        to_delete = [kb for kb in kbs if kb["name"] in target_names]

        if not to_delete:
            print("  삭제할 KB 없음")
            return

        for kb in to_delete:
            kb_id = kb["knowledgeBaseId"]
            print(f"\n  삭제 중: {kb['name']} ({kb_id})")

            # 데이터소스 먼저 삭제
            try:
                dss = agent.list_data_sources(knowledgeBaseId=kb_id).get("dataSourceSummaries", [])
                for ds in dss:
                    agent.delete_data_source(knowledgeBaseId=kb_id, dataSourceId=ds["dataSourceId"])
                    print(f"    데이터소스 삭제: {ds['name']}")
            except Exception as e:
                print(f"    DS 삭제 오류: {e}")

            # KB 삭제
            try:
                agent.delete_knowledge_base(knowledgeBaseId=kb_id)
                print(f"    ✅ KB 삭제 완료")
            except Exception as e:
                print(f"    ❌ KB 삭제 오류: {e}")

        # config 업데이트
        cfg = load_config()
        cfg.pop("text_kb_id", None)
        cfg.pop("multimodal_kb_id", None)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        print(f"\n  rag_config.json KB ID 제거 완료")
        print(f"\n  ⚠️  OpenSearch Serverless 컬렉션은 자동 삭제되지 않습니다.")
        print(f"  Console에서 직접 삭제하세요:")
        print(f"  {CONSOLE}/aos/home?region={REGION}#/collections")

    except Exception as e:
        print(f"  오류: {e}")


# ════════════════════════════════════════════════════════════════
# S3 삭제
# ════════════════════════════════════════════════════════════════
def delete_s3():
    print(f"\n{SEP}")
    print("【S3 버킷 삭제】")
    print(SEP)

    data_bucket, mm_bucket = get_bucket_names()

    for bucket in [data_bucket, mm_bucket]:
        print(f"\n  {bucket} 삭제 중...")
        try:
            s3.head_bucket(Bucket=bucket)
        except Exception:
            print(f"  이미 없음: {bucket}")
            continue

        # 모든 객체 먼저 삭제
        try:
            resp = s3.list_objects_v2(Bucket=bucket)
            objects = resp.get("Contents", [])
            if objects:
                s3.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
                )
                print(f"  {len(objects)}개 파일 삭제 완료")

            # 버전 관리 객체
            vresp = s3.list_object_versions(Bucket=bucket)
            versions = vresp.get("Versions", []) + vresp.get("DeleteMarkers", [])
            if versions:
                s3.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": v["Key"], "VersionId": v["VersionId"]}
                                         for v in versions]},
                )

            s3.delete_bucket(Bucket=bucket)
            print(f"  ✅ 버킷 삭제: {bucket}")
        except Exception as e:
            print(f"  ❌ 오류: {e}")


# ════════════════════════════════════════════════════════════════
# 실행
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG 리소스 관리")
    parser.add_argument("--delete-kb",  action="store_true", help="KB 삭제")
    parser.add_argument("--delete-s3",  action="store_true", help="S3 버킷 삭제")
    parser.add_argument("--delete-all", action="store_true", help="KB + S3 모두 삭제")
    args = parser.parse_args()

    print("=" * 60)
    print(" P3_08_rag_managed_kb.py")
    print(" RAG 실습 08 [옵션] — 리소스 상태 및 정리")
    print("=" * 60)

    if args.delete_all:
        delete_kbs()
        delete_s3()
    elif args.delete_kb:
        delete_kbs()
    elif args.delete_s3:
        delete_s3()
    else:
        print_status()
        print(f"\n  실행 옵션:")
        print(f"    --delete-kb   KB 삭제 (AOSS 컬렉션은 Console에서 수동 삭제)")
        print(f"    --delete-s3   S3 버킷 + 파일 삭제")
        print(f"    --delete-all  KB + S3 모두 삭제")

    print(f"\n{'=' * 60}")
    print("완료")
    print("=" * 60)
