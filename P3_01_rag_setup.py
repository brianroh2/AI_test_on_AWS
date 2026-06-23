"""
P3_01_rag_setup.py
────────────────────────────────────────────────────────────────────
RAG 챕터 01 — 사전 준비 확인

자동 처리:  계정/리전/모델 접근 권한 점검
사용자 필요: 없음 (확인만)

실행:
  python3 P3_01_rag_setup.py
────────────────────────────────────────────────────────────────────
"""

import boto3

REGION  = "us-east-1"
SEP     = "─" * 60
CONSOLE = f"https://{REGION}.console.aws.amazon.com"

bedrock = boto3.client("bedrock",         region_name=REGION)
sts     = boto3.client("sts",             region_name=REGION)


def step1_account():
    print(f"\n{SEP}")
    print("【STEP 1】 AWS 계정 및 리전 확인")
    print(SEP)
    identity  = sts.get_caller_identity()
    account   = identity["Account"]
    arn       = identity["Arn"]
    role_name = arn.split("/")[-2] if "assumed-role" in arn else arn.split("/")[-1]
    suffix    = account[-4:]

    print(f"  계정 ID  : {account}")
    print(f"  실행 ARN : {arn}")
    print(f"  사용 리전: {REGION}")
    print(f"\n  ✅ Knowledge Base 및 Nova Multimodal Embeddings 모두 us-east-1 지원")
    print(f"\n  【다음 실습에서 사용될 리소스 이름】")
    print(f"  S3 데이터 버킷  : telco-rateplan-kb-2026-{suffix}")
    print(f"  S3 MM 출력버킷  : telco-rateplan-kb-mm-output-2026-{suffix}")
    print(f"  텍스트 KB       : telco-rateplan-text-kb")
    print(f"  멀티모달 KB     : telco-rateplan-multimodal-kb")
    return account, role_name, suffix


def step2_model_access():
    print(f"\n{SEP}")
    print("【STEP 2】 Bedrock 모델 접근 권한 확인")
    print(SEP)
    required_models = [
        ("amazon.titan-embed-text-v2:0",            "텍스트 KB 임베딩"),
        ("amazon.nova-2-multimodal-embeddings-v1:0","멀티모달 KB 임베딩"),
        ("anthropic.claude-sonnet-4-6",              "RAG 생성 모델"),
    ]
    all_ok = True
    for model_id, desc in required_models:
        try:
            bedrock.get_foundation_model(modelIdentifier=model_id)
            print(f"  ✅ {model_id:<50s} {desc}")
        except Exception as e:
            print(f"  ❌ {model_id:<50s} {desc}")
            print(f"     오류: {e}")
            all_ok = False

    if not all_ok:
        print(f"\n  ⚠️  모델 활성화 필요:")
        print(f"  {CONSOLE}/bedrock/home?region={REGION}#/modelaccess")
    else:
        print(f"\n  ✅ 모든 필수 모델 사용 가능")
    return all_ok


def step3_permission_map():
    print(f"\n{SEP}")
    print("【STEP 3】 자동화 가능 영역 vs 사용자 직접 필요 영역")
    print(SEP)
    print("""
  ┌──────────────────────────────┬────────────┬─────────────────────────┐
  │ 작업                          │ 자동화     │ 비고                     │
  ├──────────────────────────────┼────────────┼─────────────────────────┤
  │ S3 버킷 생성 / PDF 업로드     │ ✅ 자동    │ 08 파일이 처리           │
  │ Knowledge Base 생성           │ ⚠️ 반자동  │ Console 필요 (IAM 제한)  │
  │   - IAM 서비스 역할 생성      │ ❌ Console │ iam:CreateRole 권한 없음 │
  │   - AOSS 컬렉션 자동 생성     │ ❌ Console │ aoss 권한 없음           │
  │   - KB 등록 (ARN 있을 때)     │ ✅ 자동    │ bedrock:CreateKB 있음    │
  │ KB Sync (데이터 수집)         │ ✅ 자동    │ 09 파일이 처리           │
  │ retrieve / retrieve_and_gen  │ ✅ 자동    │ 11 파일이 처리           │
  │ OpenSearch 벡터 확인          │ ✅ 자동    │ 12 파일이 처리           │
  │ Streamlit 챗봇                │ ✅ 자동    │ 13 파일이 처리           │
  └──────────────────────────────┴────────────┴─────────────────────────┘

  ★ 사용자가 직접 해야 하는 것은 KB 생성 1단계뿐입니다 ★
    → 08 실행 후 Console에서 KB 2개 생성 (~5분)
    → 이후 09~13은 완전 자동
""")


def step4_architecture():
    print(f"\n{SEP}")
    print("【STEP 4】 RAG 아키텍처 + 실습 파일 흐름")
    print(SEP)
    print("""
  [PDF 파일]
      │
      ▼  ← 08이 자동으로 업로드
  Amazon S3 (text/ / multimodal/)
      │
      ▼  ← ★ Console에서 KB 생성 (사용자 1회 수행) ★
  Bedrock Knowledge Base ──── OpenSearch Serverless (벡터 저장)
      │                   ← 09가 자동으로 Sync
      │  retrieve()
      ├─────────────────────────── 검색 결과 (청크 + 점수)  ← 11
      │  retrieve_and_generate()
      └─────► Claude Sonnet 4.6 → 답변 + citations         ← 11, 13

  파일 순서:
  ① P3_01_rag_setup.py        ← 지금 실행 중
  ② P3_02_rag_s3.py           ← S3 자동 처리
  ③ [Console] KB 2개 생성          ← 사용자 직접 (약 5분)
  ④ P3_03_rag_kb_create.py    ← Sync 자동 + KB ID 저장
  ⑤ P3_04_rag_kb_test.py      ← retrieve 자동 테스트
  ⑥ P3_05_rag_retrieve.py     ← 두 KB API 비교 자동
  ⑦ P3_06_rag_opensearch.py   ← 벡터 인덱스 자동 조회
  ⑧ P3_07_rag_chatbot.py      ← Streamlit 챗봇 자동
  ⑨ P3_08_rag_managed_kb.py   ← [옵션] 리소스 삭제 자동
""")


if __name__ == "__main__":
    print("=" * 60)
    print(" P3_01_rag_setup.py")
    print(" RAG 실습 01 — 사전 준비")
    print("=" * 60)

    account, role, suffix = step1_account()
    ok = step2_model_access()
    step3_permission_map()
    step4_architecture()

    print(f"{'=' * 60}")
    if ok:
        print("  ✅ 사전 준비 완료 → 다음: python3 P3_02_rag_s3.py")
    else:
        print("  ⚠️  모델 접근 활성화 후 재실행하세요.")
    print("=" * 60)
