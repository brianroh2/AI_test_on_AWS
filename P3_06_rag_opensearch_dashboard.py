"""
P3_06_rag_opensearch_dashboard.py
────────────────────────────────────────────────────────────────────
RAG 챕터 06 — OpenSearch Serverless 벡터 인덱스 대시보드

표시 항목:
  - KB별 카드: 상태 배지, 임베딩 모델, 컬렉션 ARN, 인덱스/필드 매핑
  - 데이터소스 / 마지막 Sync 정보
  - BDA 생성 이미지 갤러리 (멀티모달 KB)
  - Console 링크
  - AOSS 403 제약 안내 (데이터 직접 조회 불가)

실행:
  python3 -m streamlit run P3_06_rag_opensearch_dashboard.py --server.port 8505 --server.headless true &
  접속: VS Code Ports 탭 → 8505 포워딩
────────────────────────────────────────────────────────────────────
"""

import boto3
import json
import streamlit as st
from datetime import timezone
from pathlib import Path

REGION      = "us-east-1"
CONSOLE     = f"https://{REGION}.console.aws.amazon.com"
CONFIG_FILE = Path(__file__).parent / "rag_config.json"

agent = boto3.client("bedrock-agent",        region_name=REGION)
s3    = boto3.client("s3",                   region_name=REGION)
sts   = boto3.client("sts",                  region_name=REGION)

st.set_page_config(page_title="OpenSearch 벡터 대시보드", page_icon="🔍", layout="wide")

st.markdown("""
<style>
.kb-card {
    background: #1a2535; border: 1px solid #2e4a6e;
    border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 0.8rem;
}
.badge-active   { background:#1a6e38; color:#afffca; padding:2px 10px;
                  border-radius:12px; font-size:0.82rem; font-weight:700; }
.badge-inactive { background:#6e1a1a; color:#ffaaaa; padding:2px 10px;
                  border-radius:12px; font-size:0.82rem; font-weight:700; }
.field-row { font-size:0.83rem; color:#99b8d8; margin:2px 0; }
.field-key { color:#5599dd; font-weight:600; min-width:110px; display:inline-block; }
.section-title { font-size:1.05rem; font-weight:700; color:#7ec8e3;
                 border-bottom:1px solid #2e4a6e; padding-bottom:4px; margin-bottom:8px; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# 데이터 로드
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def load_kb_detail(kb_id: str) -> dict:
    kb   = agent.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]
    dss  = agent.list_data_sources(knowledgeBaseId=kb_id).get("dataSourceSummaries", [])
    ds_details = []
    for ds in dss:
        d = agent.get_data_source(
            knowledgeBaseId=kb_id, dataSourceId=ds["dataSourceId"]
        )["dataSource"]
        syncs = agent.list_ingestion_jobs(
            knowledgeBaseId=kb_id, dataSourceId=ds["dataSourceId"], maxResults=1
        ).get("ingestionJobSummaries", [])
        ds_details.append({"meta": ds, "detail": d, "last_sync": syncs[0] if syncs else None})
    return {"kb": kb, "ds_list": ds_details}


@st.cache_data(ttl=30)
def load_mm_images(bucket: str, prefix: str = "aws/bedrock/knowledge_bases/") -> list:
    """멀티모달 output 버킷에서 BDA 생성 PNG 목록 로드"""
    try:
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return [o for o in resp.get("Contents", []) if o["Key"].endswith(".png")]
    except Exception:
        return []


@st.cache_data(ttl=60)
def get_image_bytes(bucket: str, key: str) -> bytes:
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def get_mm_bucket() -> str:
    account = sts.get_caller_identity()["Account"]
    return f"telco-rateplan-kb-mm-output-2026-{account[-4:]}"


# ════════════════════════════════════════════════════════════════
# 헬퍼
# ════════════════════════════════════════════════════════════════

def status_badge(status: str) -> str:
    if status == "ACTIVE":
        return '<span class="badge-active">● ACTIVE</span>'
    return f'<span class="badge-inactive">● {status}</span>'


def shorten_arn(arn: str) -> str:
    parts = arn.split(":")
    return "…:" + parts[-1] if len(parts) > 5 else arn


def model_label(arn: str) -> str:
    model_id = arn.split("/")[-1]
    labels = {
        "amazon.titan-embed-text-v2:0":            "Titan Text Embeddings V2  (dim 1024)",
        "amazon.nova-2-multimodal-embeddings-v1:0": "Nova Multimodal Embeddings (dim 3072)",
    }
    return labels.get(model_id, model_id)


# ════════════════════════════════════════════════════════════════
# 사이드바
# ════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(f"""
<div style='background:#1e3a5f;border-radius:8px;padding:0.5rem 0.8rem;margin-bottom:0.5rem;
            font-size:0.95rem;line-height:1.8;color:#e0e0e0;'>
  🔍 OpenSearch 대시보드<br>
  🌏 <span style='color:#7ec8e3;font-weight:600;'>{REGION}</span>
</div>
""", unsafe_allow_html=True)

    if st.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("""
<p style='font-size:0.82rem;color:#99b8d8;'>
⚠️ <b>AOSS 직접 조회 제약</b><br>
SageMaker 실행 역할에<br>
aoss:BatchGetCollection 권한 없음.<br><br>
벡터 인덱스 매핑·청크 수는<br>
아래 Console에서 확인하세요.
</p>
""", unsafe_allow_html=True)

    st.markdown(
        f"[🔗 OpenSearch Console]({CONSOLE}/aos/home?region={REGION}#/collections)"
    )
    st.markdown(
        f"[🔗 Bedrock KB Console]({CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases)"
    )


# ════════════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════════════

st.title("🔍 OpenSearch Serverless 벡터 인덱스 대시보드")

# ── config 로드 ────────────────────────────────────────────────
if not CONFIG_FILE.exists():
    st.error("rag_config.json 없음 — P3_03_rag_kb_create.py 를 먼저 실행하세요.")
    st.stop()

cfg = json.loads(CONFIG_FILE.read_text())
kb_map = {
    "📝 텍스트 KB": cfg.get("text_kb_id", ""),
    "🖼️ 멀티모달 KB": cfg.get("multimodal_kb_id", ""),
}
kb_map = {k: v for k, v in kb_map.items() if v}
if not kb_map:
    st.error("KB ID가 없습니다. P3_03 을 다시 실행하세요.")
    st.stop()

# ── KB 카드 2열 ────────────────────────────────────────────────
cols = st.columns(2)

for col, (label, kb_id) in zip(cols, kb_map.items()):
    with col:
        with st.spinner(f"{label} 로딩 중..."):
            try:
                data   = load_kb_detail(kb_id)
                kb     = data["kb"]
                ds_list = data["ds_list"]
            except Exception as e:
                st.error(f"KB 조회 오류: {e}")
                continue

        sc       = kb.get("storageConfiguration", {})
        oss      = sc.get("opensearchServerlessConfiguration", {})
        fm       = oss.get("fieldMapping", {})
        emb_arn  = (kb.get("knowledgeBaseConfiguration", {})
                      .get("vectorKnowledgeBaseConfiguration", {})
                      .get("embeddingModelArn", ""))
        col_arn  = oss.get("collectionArn", "")
        col_id   = col_arn.split("/")[-1] if col_arn else ""
        idx_name = oss.get("vectorIndexName", "")

        st.markdown(f"### {label}")
        st.markdown(
            f'<div class="kb-card">'
            f'<div style="margin-bottom:6px;">'
            f'  <b style="font-size:1rem;">{kb["name"]}</b>&nbsp;&nbsp;'
            f'  {status_badge(kb["status"])}'
            f'</div>'
            f'<div class="field-row"><span class="field-key">KB ID</span>{kb_id}</div>'
            f'<div class="field-row"><span class="field-key">임베딩 모델</span>{model_label(emb_arn)}</div>'
            f'<div class="field-row"><span class="field-key">컬렉션 ID</span>{col_id}</div>'
            f'<div class="field-row"><span class="field-key">인덱스 이름</span>{idx_name}</div>'
            f'<div class="field-row"><span class="field-key">벡터 필드</span>{fm.get("vectorField","")}</div>'
            f'<div class="field-row"><span class="field-key">텍스트 필드</span>{fm.get("textField","")}</div>'
            f'<div class="field-row"><span class="field-key">메타 필드</span>{fm.get("metadataField","")}</div>'
            f'<div class="field-row"><span class="field-key">생성일</span>'
            f'  {kb["createdAt"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # 데이터소스 + Sync 상태
        st.markdown('<div class="section-title">📂 데이터소스 & Sync</div>',
                    unsafe_allow_html=True)
        for ds_info in ds_list:
            ds     = ds_info["detail"]
            sync   = ds_info["last_sync"]
            s3cfg  = ds.get("dataSourceConfiguration", {}).get("s3Configuration", {})
            prefix = s3cfg.get("inclusionPrefixes", [])
            s_icon = "✅" if ds_info["meta"]["status"] == "AVAILABLE" else "⏳"
            st.markdown(
                f"{s_icon} **{ds['name']}**  `{ds_info['meta']['status']}`"
            )
            st.caption(f"S3 prefix: {prefix}")
            if sync:
                sync_icon = "✅" if sync["status"] == "COMPLETE" else "⏳"
                updated = sync["updatedAt"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                st.caption(f"{sync_icon} 마지막 Sync: **{sync['status']}** ({updated})")

        # Console 링크
        st.markdown(
            f"[🔗 KB Console]({CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases/{kb_id})  "
            f"[🔗 AOSS Collections]({CONSOLE}/aos/home?region={REGION}#/collections)"
        )

        # AOSS 직접 조회 안내
        with st.expander("🔎 인덱스 상세 확인 방법 (Console)"):
            st.markdown(f"""
1. [OpenSearch Collections]({CONSOLE}/aos/home?region={REGION}#/collections) 접속
2. 컬렉션 `{col_id}` 클릭
3. **Indexes** 탭 → `{idx_name}` 클릭
4. **Mappings** 탭 → `bedrock-knowledge-base-default-vector` 필드 확인
   (`type: knn_vector`, `dimension: {1024 if "titan" in emb_arn else 3072}`)
5. **Documents** 탭 → 인덱싱된 청크 수 확인
""")

st.markdown("---")

# ── BDA 생성 이미지 갤러리 (멀티모달 KB) ──────────────────────
st.markdown("## 🖼️ BDA 생성 이미지 갤러리 (멀티모달 KB)")
st.caption("Bedrock Data Automation이 PDF를 파싱하며 추출한 이미지/슬라이드 청크입니다.")

mm_bucket = get_mm_bucket()
images    = load_mm_images(mm_bucket)

if not images:
    st.info(f"이미지 없음 (버킷: {mm_bucket})")
else:
    st.success(f"총 **{len(images)}개** 이미지 — 버킷: `{mm_bucket}`")

    # 페이지네이션
    PAGE_SIZE = 6
    total_pages = (len(images) - 1) // PAGE_SIZE + 1
    page = st.number_input("페이지", min_value=1, max_value=total_pages,
                           value=1, step=1, label_visibility="collapsed")
    start = (page - 1) * PAGE_SIZE
    page_imgs = images[start: start + PAGE_SIZE]

    st.caption(f"페이지 {page} / {total_pages}  ({start+1}~{min(start+PAGE_SIZE, len(images))} / {len(images)})")

    img_cols = st.columns(3)
    for i, obj in enumerate(page_imgs):
        with img_cols[i % 3]:
            try:
                img_bytes = get_image_bytes(mm_bucket, obj["Key"])
                fname     = obj["Key"].split("/")[-1][:24]
                size_kb   = obj["Size"] // 1024
                updated   = obj["LastModified"].strftime("%H:%M")
                st.image(img_bytes, caption=f"{fname}  ({size_kb}KB, {updated})",
                         use_container_width=True)
            except Exception as e:
                st.warning(f"이미지 로드 실패: {e}")

# ── 하단 정보 ──────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "💡 벡터 인덱스 직접 조회(kNN 검색)는 AOSS 데이터 접근 정책에 "
    "SageMaker 실행 역할 추가 후 P3_06_rag_opensearch.py 로 실행하세요."
)
