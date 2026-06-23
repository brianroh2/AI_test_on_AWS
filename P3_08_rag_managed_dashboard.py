"""
P3_08_rag_managed_dashboard.py
────────────────────────────────────────────────────────────────────
RAG 챕터 08 — 리소스 관리 대시보드

표시 항목:
  - KB 상태 카드 (ACTIVE 배지, ID, 생성일, Sync 이력)
  - S3 버킷 파일 목록 (파일명, 크기, 업로드일)
  - rag_config.json 현재 값
  - KB 삭제 / S3 삭제 버튼 (확인 다이얼로그 포함)

실행:
  python3 -m streamlit run P3_08_rag_managed_dashboard.py --server.port 8506 --server.headless true &
  접속: VS Code Ports 탭 → 8506 포워딩
────────────────────────────────────────────────────────────────────
"""

import boto3
import json
import time
import streamlit as st
from datetime import timezone
from pathlib import Path

REGION      = "us-east-1"
CONSOLE     = f"https://{REGION}.console.aws.amazon.com"
CONFIG_FILE = Path(__file__).parent / "rag_config.json"
TARGET_KB_NAMES = {"telco-rateplan-text-kb", "telco-rateplan-multimodal-kb"}

agent = boto3.client("bedrock-agent", region_name=REGION)
s3    = boto3.client("s3",            region_name=REGION)
sts   = boto3.client("sts",           region_name=REGION)

st.set_page_config(page_title="RAG 리소스 관리", page_icon="🛠️", layout="wide")

st.markdown("""
<style>
.res-card {
    background:#1a2535; border:1px solid #2e4a6e;
    border-radius:10px; padding:0.9rem 1.1rem; margin-bottom:0.7rem;
}
.badge-active   { background:#1a6e38; color:#afffca; padding:2px 10px;
                  border-radius:12px; font-size:0.82rem; font-weight:700; }
.badge-inactive { background:#6e1a1a; color:#ffaaaa; padding:2px 10px;
                  border-radius:12px; font-size:0.82rem; font-weight:700; }
.badge-warn     { background:#6e4e1a; color:#ffd9a0; padding:2px 10px;
                  border-radius:12px; font-size:0.82rem; font-weight:700; }
.field-row { font-size:0.83rem; color:#99b8d8; margin:3px 0; }
.field-key { color:#5599dd; font-weight:600; min-width:110px; display:inline-block; }
.section-title { font-size:1.0rem; font-weight:700; color:#7ec8e3;
                 border-bottom:1px solid #2e4a6e; padding-bottom:4px; margin-bottom:8px; }
.danger-zone { border:1px solid #8b2020; border-radius:8px;
               padding:0.8rem 1rem; background:#1a0e0e; margin-top:0.5rem; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# 데이터 로드
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=20)
def load_all_kbs() -> list:
    return agent.list_knowledge_bases(maxResults=20).get("knowledgeBaseSummaries", [])


@st.cache_data(ttl=20)
def load_kb_sync(kb_id: str) -> list:
    dss = agent.list_data_sources(knowledgeBaseId=kb_id).get("dataSourceSummaries", [])
    result = []
    for ds in dss:
        syncs = agent.list_ingestion_jobs(
            knowledgeBaseId=kb_id, dataSourceId=ds["dataSourceId"], maxResults=3
        ).get("ingestionJobSummaries", [])
        result.append({"ds": ds, "syncs": syncs})
    return result


@st.cache_data(ttl=20)
def load_s3_objects(bucket: str) -> list:
    try:
        resp = s3.list_objects_v2(Bucket=bucket)
        return resp.get("Contents", [])
    except Exception:
        return []


@st.cache_data(ttl=60)
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


def status_badge(status: str) -> str:
    if status == "ACTIVE":
        return '<span class="badge-active">● ACTIVE</span>'
    if status in ("DELETING", "FAILED"):
        return f'<span class="badge-inactive">● {status}</span>'
    return f'<span class="badge-warn">● {status}</span>'


def sync_badge(status: str) -> str:
    if status == "COMPLETE":
        return "✅ COMPLETE"
    if status == "FAILED":
        return "❌ FAILED"
    return f"⏳ {status}"


# ════════════════════════════════════════════════════════════════
# 삭제 함수
# ════════════════════════════════════════════════════════════════

def do_delete_kbs(kb_ids: list[str]) -> list[str]:
    msgs = []
    for kb_id in kb_ids:
        try:
            dss = agent.list_data_sources(knowledgeBaseId=kb_id).get("dataSourceSummaries", [])
            for ds in dss:
                agent.delete_data_source(knowledgeBaseId=kb_id, dataSourceId=ds["dataSourceId"])
            agent.delete_knowledge_base(knowledgeBaseId=kb_id)
            msgs.append(f"✅ KB 삭제 완료: {kb_id}")
        except Exception as e:
            msgs.append(f"❌ KB 삭제 오류 ({kb_id}): {e}")
    # config 업데이트
    cfg = load_config()
    cfg.pop("text_kb_id", None)
    cfg.pop("multimodal_kb_id", None)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    msgs.append("📝 rag_config.json KB ID 제거 완료")
    return msgs


def do_delete_s3(buckets: list[str]) -> list[str]:
    msgs = []
    for bucket in buckets:
        try:
            s3.head_bucket(Bucket=bucket)
        except Exception:
            msgs.append(f"⏭️ 이미 없음: {bucket}")
            continue
        try:
            resp = s3.list_objects_v2(Bucket=bucket)
            objs = resp.get("Contents", [])
            if objs:
                s3.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": o["Key"]} for o in objs]},
                )
            vresp = s3.list_object_versions(Bucket=bucket)
            versions = vresp.get("Versions", []) + vresp.get("DeleteMarkers", [])
            if versions:
                s3.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": v["Key"], "VersionId": v["VersionId"]}
                                        for v in versions]},
                )
            s3.delete_bucket(Bucket=bucket)
            msgs.append(f"✅ S3 버킷 삭제 완료: {bucket}")
        except Exception as e:
            msgs.append(f"❌ S3 삭제 오류 ({bucket}): {e}")
    return msgs


# ════════════════════════════════════════════════════════════════
# 세션 상태 초기화
# ════════════════════════════════════════════════════════════════

for k, v in {
    "confirm_delete_kb": False,
    "confirm_delete_s3": False,
    "op_result": [],
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ════════════════════════════════════════════════════════════════
# 사이드바
# ════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(f"""
<div style='background:#1e3a5f;border-radius:8px;padding:0.5rem 0.8rem;margin-bottom:0.5rem;
            font-size:0.95rem;line-height:1.8;color:#e0e0e0;'>
  🛠️ RAG 리소스 관리<br>
  🌏 <span style='color:#7ec8e3;font-weight:600;'>{REGION}</span>
</div>
""", unsafe_allow_html=True)

    if st.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.session_state.op_result = []
        st.rerun()

    st.markdown("---")
    st.markdown(f"[🔗 Bedrock KB Console]({CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases)")
    st.markdown(f"[🔗 S3 Console](https://s3.console.aws.amazon.com/s3/buckets?region={REGION})")
    st.markdown(f"[🔗 AOSS Console]({CONSOLE}/aos/home?region={REGION}#/collections)")

    st.markdown("---")
    st.markdown("""
<p style='font-size:0.8rem;color:#99b8d8;'>
⚠️ <b>OpenSearch 컬렉션</b>은<br>
자동 삭제 불가<br>
(aoss 권한 없음)<br>
→ AOSS Console에서 수동 삭제
</p>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════════════

st.title("🛠️ RAG 리소스 관리 대시보드")

# ── 작업 결과 표시 ─────────────────────────────────────────────
if st.session_state.op_result:
    with st.container():
        for msg in st.session_state.op_result:
            if msg.startswith("✅"):
                st.success(msg)
            elif msg.startswith("❌"):
                st.error(msg)
            else:
                st.info(msg)
    st.markdown("---")

data_bucket, mm_bucket = get_bucket_names()

# ════════════════════════════════════════════════════════════════
# 섹션 1: Knowledge Base 상태
# ════════════════════════════════════════════════════════════════

st.markdown("## 📚 Knowledge Base 상태")

with st.spinner("KB 목록 로딩 중..."):
    try:
        all_kbs = load_all_kbs()
        target_kbs = [kb for kb in all_kbs if kb["name"] in TARGET_KB_NAMES]
    except Exception as e:
        st.error(f"KB 목록 조회 오류: {e}")
        target_kbs = []

if not target_kbs:
    st.warning("대상 KB가 없습니다. P3_03 실행 후 KB를 생성하세요.")
else:
    kb_cols = st.columns(len(target_kbs))
    delete_kb_ids = []

    for col, kb in zip(kb_cols, target_kbs):
        with col:
            kb_id = kb["knowledgeBaseId"]
            delete_kb_ids.append(kb_id)

            st.markdown(
                f'<div class="res-card">'
                f'<div style="margin-bottom:6px;">'
                f'  <b style="font-size:0.95rem;">{kb["name"]}</b>&nbsp;&nbsp;'
                f'  {status_badge(kb["status"])}'
                f'</div>'
                f'<div class="field-row"><span class="field-key">KB ID</span>{kb_id}</div>'
                f'<div class="field-row"><span class="field-key">업데이트</span>'
                f'{kb["updatedAt"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Sync 이력
            st.markdown('<div class="section-title">🔄 Sync 이력</div>',
                        unsafe_allow_html=True)
            try:
                ds_syncs = load_kb_sync(kb_id)
                for item in ds_syncs:
                    st.markdown(f"**{item['ds']['name']}**")
                    if item["syncs"]:
                        for sync in item["syncs"]:
                            updated = sync["updatedAt"].astimezone(timezone.utc).strftime("%m-%d %H:%M")
                            st.caption(f"{sync_badge(sync['status'])}  {updated}")
                    else:
                        st.caption("Sync 이력 없음")
            except Exception as e:
                st.caption(f"조회 오류: {e}")

            st.markdown(
                f"[🔗 Console]({CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases/{kb_id})"
            )

st.markdown("---")

# ════════════════════════════════════════════════════════════════
# 섹션 2: S3 버킷 상태
# ════════════════════════════════════════════════════════════════

st.markdown("## 🪣 S3 버킷 상태")

s3_cols = st.columns(2)

for col, bucket in zip(s3_cols, [data_bucket, mm_bucket]):
    with col:
        objs = load_s3_objects(bucket)
        total_kb = sum(o["Size"] for o in objs) // 1024

        bucket_label = "📥 데이터 소스 버킷" if bucket == data_bucket else "🖼️ 멀티모달 출력 버킷"
        st.markdown(f"**{bucket_label}**")

        if not objs:
            st.markdown(
                f'<div class="res-card">'
                f'<span class="badge-inactive">● 없음 또는 비어있음</span><br>'
                f'<div class="field-row" style="margin-top:6px;">{bucket}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="res-card">'
                f'<span class="badge-active">● 존재</span>&nbsp;&nbsp;'
                f'<span style="font-size:0.85rem;color:#afffca;">'
                f'{len(objs)}개 파일 · {total_kb} KB</span><br>'
                f'<div class="field-row" style="margin-top:6px;">{bucket}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # 파일 목록 테이블
            rows = []
            for o in sorted(objs, key=lambda x: x["Key"]):
                fname   = o["Key"].split("/")[-1] or o["Key"]
                size_kb = o["Size"] // 1024 or 1
                updated = o["LastModified"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
                rows.append({"파일명": fname, "크기(KB)": size_kb, "업로드": updated})
            st.dataframe(rows, use_container_width=True, hide_index=True)

        st.markdown(
            f"[🔗 S3 Console](https://s3.console.aws.amazon.com/s3/buckets/{bucket}?region={REGION})"
        )

st.markdown("---")

# ════════════════════════════════════════════════════════════════
# 섹션 3: rag_config.json
# ════════════════════════════════════════════════════════════════

st.markdown("## 📋 rag_config.json")
cfg = load_config()
if cfg:
    cfg_cols = st.columns(len(cfg))
    for col, (k, v) in zip(cfg_cols, cfg.items()):
        with col:
            st.markdown(
                f'<div class="res-card">'
                f'<div class="field-row"><span class="field-key">{k}</span></div>'
                f'<div style="font-size:0.9rem;color:#ffffff;margin-top:4px;">{v}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
else:
    st.info("rag_config.json 없거나 비어있음")

st.markdown("---")

# ════════════════════════════════════════════════════════════════
# 섹션 4: 리소스 삭제
# ════════════════════════════════════════════════════════════════

st.markdown("## 🗑️ 리소스 삭제")

with st.container():
    st.markdown('<div class="danger-zone">', unsafe_allow_html=True)

    del_col1, del_col2, del_col3 = st.columns(3)

    # ── KB 삭제 ─────────────────────────────────────────────────
    with del_col1:
        st.markdown("**📚 KB 삭제**")
        st.caption(f"대상: {', '.join(TARGET_KB_NAMES)}")
        if not st.session_state.confirm_delete_kb:
            if st.button("🗑️ KB 삭제", type="secondary", use_container_width=True,
                         disabled=not bool(target_kbs)):
                st.session_state.confirm_delete_kb = True
                st.rerun()
        else:
            st.warning("정말 삭제하시겠습니까?")
            c1, c2 = st.columns(2)
            if c1.button("✅ 확인", type="primary", use_container_width=True):
                with st.spinner("KB 삭제 중..."):
                    st.session_state.op_result = do_delete_kbs(delete_kb_ids)
                st.session_state.confirm_delete_kb = False
                st.cache_data.clear()
                st.rerun()
            if c2.button("❌ 취소", use_container_width=True):
                st.session_state.confirm_delete_kb = False
                st.rerun()

    # ── S3 삭제 ─────────────────────────────────────────────────
    with del_col2:
        st.markdown("**🪣 S3 삭제**")
        st.caption(f"데이터 버킷 + 멀티모달 출력 버킷")
        if not st.session_state.confirm_delete_s3:
            if st.button("🗑️ S3 삭제", type="secondary", use_container_width=True):
                st.session_state.confirm_delete_s3 = True
                st.rerun()
        else:
            st.warning("정말 삭제하시겠습니까?")
            c1, c2 = st.columns(2)
            if c1.button("✅ 확인", type="primary", use_container_width=True,
                         key="s3_confirm"):
                with st.spinner("S3 삭제 중..."):
                    st.session_state.op_result = do_delete_s3([data_bucket, mm_bucket])
                st.session_state.confirm_delete_s3 = False
                st.cache_data.clear()
                st.rerun()
            if c2.button("❌ 취소", use_container_width=True, key="s3_cancel"):
                st.session_state.confirm_delete_s3 = False
                st.rerun()

    # ── 전체 삭제 ───────────────────────────────────────────────
    with del_col3:
        st.markdown("**⚠️ 전체 삭제 (KB + S3)**")
        st.caption("KB와 S3 버킷을 모두 삭제합니다.")
        if st.button("🗑️ 전체 삭제", type="secondary", use_container_width=True,
                     disabled=not bool(target_kbs)):
            with st.spinner("전체 삭제 중..."):
                msgs  = do_delete_kbs(delete_kb_ids)
                msgs += do_delete_s3([data_bucket, mm_bucket])
                st.session_state.op_result = msgs
            st.cache_data.clear()
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.caption("⚠️ OpenSearch Serverless 컬렉션은 자동 삭제 불가 → "
           f"[AOSS Console]({CONSOLE}/aos/home?region={REGION}#/collections) 에서 수동 삭제")
