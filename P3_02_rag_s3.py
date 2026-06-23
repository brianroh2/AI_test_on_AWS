"""
P3_02_rag_s3.py
────────────────────────────────────────────────────────────────────
RAG 챕터 02 — S3 버킷 생성과 PDF 업로드

목표:
  - 데이터 버킷 생성 (text/ + multimodal/ prefix)
  - MM output 버킷 생성 (BDA 멀티모달 파싱 결과 저장용)
  - 두 PDF 파일 업로드
  - AWS Console 확인 URL 출력

버킷 이름 규칙:
  telco-rateplan-kb-2026-<계정마지막4자리>
  telco-rateplan-kb-mm-output-2026-<계정마지막4자리>

실행:
  python3 P3_02_rag_s3.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import glob
import os
import sys
from pathlib import Path
import unicodedata

REGION = "us-east-1"
SEP    = "─" * 60

# ── PDF 경로: 한국어 파일명은 NFD 정규화로 저장될 수 있으므로 glob으로 탐색 ──
SCRIPT_DIR = Path(__file__).parent

def _find_pdf(keyword: str) -> Path | None:
    """SCRIPT_DIR에서 keyword를 포함하는 PDF 파일을 NFD/NFC 무관하게 찾는다."""
    for f in glob.glob(str(SCRIPT_DIR / "*.pdf")):
        name_nfc = unicodedata.normalize("NFC", os.path.basename(f))
        if unicodedata.normalize("NFC", keyword) in name_nfc:
            return Path(f)
    return None

TEXT_PDF       = _find_pdf("텍스트형")
MULTIMODAL_PDF = _find_pdf("멀티모달형")

s3  = boto3.client("s3",  region_name=REGION)
sts = boto3.client("sts", region_name=REGION)


# ═══════════════════════════════════════════════════════════════
# 버킷 이름 결정
# ═══════════════════════════════════════════════════════════════
def get_bucket_names() -> tuple[str, str]:
    account = sts.get_caller_identity()["Account"]
    suffix  = account[-4:]
    return (
        f"telco-rateplan-kb-2026-{suffix}",
        f"telco-rateplan-kb-mm-output-2026-{suffix}",
    )


# ═══════════════════════════════════════════════════════════════
# 버킷 생성 (이미 존재하면 재사용)
# ═══════════════════════════════════════════════════════════════
def create_bucket(bucket_name: str) -> bool:
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"  ✅ 이미 존재: {bucket_name}")
        return True
    except s3.exceptions.ClientError as e:
        code = e.response["Error"]["Code"]
        if code not in ("404", "NoSuchBucket"):
            # 다른 계정 소유 등 접근 불가
            print(f"  ❌ 버킷 접근 오류: {bucket_name} — {e}")
            return False

    # 생성
    try:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        # Public access block (보안)
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        print(f"  ✅ 생성 완료: {bucket_name}")
        return True
    except Exception as e:
        print(f"  ❌ 생성 실패: {bucket_name} — {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# PDF 업로드
# ═══════════════════════════════════════════════════════════════
def upload_pdf(local_path: Path | None, bucket: str, s3_key: str) -> bool:
    if local_path is None or not local_path.exists():
        print(f"  ❌ 로컬 파일 없음: {local_path}")
        return False

    size_kb = local_path.stat().st_size // 1024
    try:
        # 이미 업로드 됐으면 건너뜀
        s3.head_object(Bucket=bucket, Key=s3_key)
        print(f"  ✅ 이미 업로드됨: s3://{bucket}/{s3_key} ({size_kb}KB)")
        return True
    except s3.exceptions.ClientError:
        pass

    try:
        s3.upload_file(str(local_path), bucket, s3_key)
        print(f"  ✅ 업로드 완료 : s3://{bucket}/{s3_key} ({size_kb}KB)")
        return True
    except Exception as e:
        print(f"  ❌ 업로드 실패 : {s3_key} — {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# S3 목록 확인
# ═══════════════════════════════════════════════════════════════
def verify_s3(data_bucket: str):
    print(f"\n  버킷 내 파일 목록:")
    try:
        resp = s3.list_objects_v2(Bucket=data_bucket)
        for obj in resp.get("Contents", []):
            print(f"    {obj['LastModified'].strftime('%Y-%m-%d %H:%M')}  "
                  f"{obj['Size']:>8,}  {obj['Key']}")
    except Exception as e:
        print(f"  목록 조회 오류: {e}")


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(" P3_02_rag_s3.py")
    print(" RAG 실습 02 — S3 버킷 생성과 PDF 업로드")
    print("=" * 60)

    DATA_BUCKET, MM_BUCKET = get_bucket_names()
    print(f"\n  데이터 버킷 : {DATA_BUCKET}")
    print(f"  MM 출력버킷 : {MM_BUCKET}")

    # ── 버킷 생성 ───────────────────────────────────────────────
    print(f"\n{SEP}")
    print("【STEP 1】 S3 버킷 생성")
    print(SEP)
    ok1 = create_bucket(DATA_BUCKET)
    ok2 = create_bucket(MM_BUCKET)

    if not (ok1 and ok2):
        print("\n  버킷 생성 실패. 종료합니다.")
        sys.exit(1)

    # ── PDF 업로드 ──────────────────────────────────────────────
    print(f"\n{SEP}")
    print("【STEP 2】 PDF 업로드 (text/ / multimodal/ prefix)")
    print(SEP)

    uploads = [
        (TEXT_PDF,       DATA_BUCKET, "text/통신사_요금제_텍스트형.pdf"),
        (MULTIMODAL_PDF, DATA_BUCKET, "multimodal/통신사_요금제_멀티모달형.pdf"),
    ]
    results = [upload_pdf(p, b, k) for p, b, k in uploads]

    # ── 업로드 확인 ─────────────────────────────────────────────
    print(f"\n{SEP}")
    print("【STEP 3】 업로드 결과 확인")
    print(SEP)
    verify_s3(DATA_BUCKET)

    # ── AWS Console 확인 가이드 ─────────────────────────────────
    print(f"\n{SEP}")
    print("【AWS Console 확인】")
    print(SEP)
    print(f"\n  S3 버킷 목록:")
    print(f"  https://s3.console.aws.amazon.com/s3/buckets?region={REGION}")
    print(f"\n  데이터 버킷 내용:")
    print(f"  https://s3.console.aws.amazon.com/s3/buckets/{DATA_BUCKET}?region={REGION}&tab=objects")
    print(f"\n  MM 출력 버킷:")
    print(f"  https://s3.console.aws.amazon.com/s3/buckets/{MM_BUCKET}?region={REGION}&tab=objects")
    print(f"\n  ◎ Console 확인 포인트:")
    print(f"     - text/ 폴더에 텍스트형 PDF 존재")
    print(f"     - multimodal/ 폴더에 멀티모달형 PDF 존재")
    print(f"     - 두 파일 모두 Public access 차단 상태")

    print(f"\n{SEP}")
    print("【다음 단계】 — Knowledge Base 생성 (AWS Console)")
    print(SEP)
    print(f"""
  AWS Console에서 Knowledge Base 두 개를 생성하세요:

  A. telco-rateplan-text-kb (텍스트 전용)
     Amazon Bedrock > Knowledge Bases > Create knowledge base
     > Unstructured Vector Store KB
     - 이름: telco-rateplan-text-kb
     - IAM: Create and use a new service role
     - 데이터 소스: Amazon S3
       S3 URI: s3://{DATA_BUCKET}/text/
     - 파서  : Default parser
     - 임베딩: Titan Text Embeddings V2
     - 벡터 DB: Quick create → Amazon OpenSearch Serverless

  B. telco-rateplan-multimodal-kb (멀티모달)
     - 이름: telco-rateplan-multimodal-kb
     - 데이터 소스:
       S3 URI: s3://{DATA_BUCKET}/multimodal/
       파서: Amazon Bedrock Data Automation (BDA)
       MM output bucket: {MM_BUCKET}
     - 임베딩: Amazon Nova Multimodal Embeddings
               (amazon.nova-2-multimodal-embeddings-v1:0, dim=3072)
     - 벡터 DB: Quick create → Amazon OpenSearch Serverless

  생성 후 P3_03_rag_kb_create.py 를 실행하세요.
""")

    print(f"{'=' * 60}")
    print("완료")
    print("=" * 60)
