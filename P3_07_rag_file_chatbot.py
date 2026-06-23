"""
P3_07_rag_file_chatbot.py
────────────────────────────────────────────────────────────────────
RAG 챕터 07 확장 — KB 챗봇 + 파일 업로드 RAG 챗봇

사이드바:
  [모델 / 리전 정보] ← 최상단, 2줄, 글자 약간 크게
  [📚 KB 챗봇 / 📄 파일 챗봇] ← 라디오 선택
  [선택된 모드의 세부 설정만 펼쳐서 표시]

메인: 선택된 챗봇 단독 풀너비 표시 (탭 없음)

실행:
  python3 -m streamlit run P3_07_rag_file_chatbot.py --server.port 8504 --server.headless true &
  접속: VS Code Ports 탭 → 8504 포워딩
────────────────────────────────────────────────────────────────────
"""

import boto3
import json
import re
import streamlit as st
from pathlib import Path

REGION        = "us-east-1"
CONSOLE       = f"https://{REGION}.console.aws.amazon.com"
CONFIG_FILE   = Path(__file__).parent / "rag_config.json"
GEN_MODEL_ID  = "us.anthropic.claude-sonnet-4-6"
_ACCOUNT_ID   = boto3.client("sts").get_caller_identity()["Account"]
GEN_MODEL_ARN = f"arn:aws:bedrock:{REGION}:{_ACCOUNT_ID}:inference-profile/{GEN_MODEL_ID}"

agent_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)
bedrock_rt    = boto3.client("bedrock-runtime",       region_name=REGION)

st.set_page_config(
    page_title="RAG 챗봇",
    page_icon="🗂️",
    layout="wide",
)

st.markdown("""
<style>
/* 사이드바 폭 고정 */
[data-testid="stSidebar"] { min-width: 270px; max-width: 270px; }
[data-testid="stSidebar"] .block-container { padding-top: 0.8rem; }

/* 최상단 모델/리전 텍스트 */
.sidebar-info { font-size: 0.95rem; line-height: 1.7; color: #e0e0e0;
                background: #1e3a5f; border-radius: 6px;
                padding: 0.45rem 0.7rem; margin-bottom: 0.6rem; }
.sidebar-info span { color: #7ec8e3; font-weight: 600; }

/* 라디오 그룹 — 챗봇 선택 */
[data-testid="stSidebar"] .stRadio > label { display: none; }
[data-testid="stSidebar"] .stRadio {
    border: 2px solid #cccccc;
    border-radius: 10px;
    padding: 0.5rem 0.6rem;
    background: #f5f5f5; }
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] { gap: 0.4rem; }
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: #222222 !important;
    background: #ffffff;
    border: 1px solid #bbbbbb;
    border-radius: 7px;
    padding: 0.45rem 0.8rem; }
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label:has(input:checked) {
    background: #1a6ed8;
    border: 2px solid #1a6ed8;
    color: #ffffff !important; }

/* 구분선 */
[data-testid="stSidebar"] hr { margin: 0.5rem 0; }

/* 일반 텍스트 / 버튼 간격 */
[data-testid="stSidebar"] p  { font-size: 0.82rem; margin-bottom: 0.15rem; }
[data-testid="stSidebar"] .stButton button {
    padding: 0.2rem 0.5rem; font-size: 0.78rem; margin-bottom: 0.1rem; }
[data-testid="stSidebar"] .stCheckbox   { margin-bottom: 0.1rem; }
[data-testid="stSidebar"] .stSelectbox  { margin-bottom: 0.1rem; }
[data-testid="stSidebar"] .stAlert      { padding: 0.3rem 0.5rem; font-size: 0.78rem; }
[data-testid="stSidebar"] .stCodeBlock  { margin: 0.1rem 0; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# 공통 유틸
# ════════════════════════════════════════════════════════════════

@st.cache_data
def load_kb_ids() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
        return {
            "텍스트 KB (Titan)":  cfg.get("text_kb_id", ""),
            "멀티모달 KB (Nova)": cfg.get("multimodal_kb_id", ""),
        }
    except Exception:
        return {}


def safe_doc_name(filename: str) -> str:
    stem    = Path(filename).stem
    cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '_', stem)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned[:100] or "document"


def detect_modality(pdf_bytes: bytes) -> str:
    sample = pdf_bytes[:min(len(pdf_bytes), 65536)]
    return "multimodal" if sample.count(b"/Image") > sample.count(b"BT") * 0.5 else "text"


# ════════════════════════════════════════════════════════════════
# KB / 파일 챗봇 로직
# ════════════════════════════════════════════════════════════════

def kb_ask(kb_id: str, question: str) -> tuple[str, list]:
    resp = agent_runtime.retrieve_and_generate(
        input={"text": question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb_id,
                "modelArn":        GEN_MODEL_ARN,
            },
        },
    )
    return resp["output"]["text"], resp.get("citations", [])


def build_converse_messages(chat_history, new_question, pdf_bytes, doc_name):
    messages        = []
    first_user_done = False
    for msg in chat_history:
        if msg["role"] == "user" and not first_user_done and pdf_bytes:
            messages.append({"role": "user", "content": [
                {"document": {"name": doc_name, "format": "pdf",
                              "source": {"bytes": pdf_bytes}}},
                {"text": msg["content"]},
            ]})
            first_user_done = True
        else:
            messages.append({"role": msg["role"],
                             "content": [{"text": msg["content"]}]})
    if not first_user_done and pdf_bytes:
        messages.append({"role": "user", "content": [
            {"document": {"name": doc_name, "format": "pdf",
                          "source": {"bytes": pdf_bytes}}},
            {"text": new_question},
        ]})
    else:
        messages.append({"role": "user", "content": [{"text": new_question}]})
    return messages


def file_ask(pdf_bytes, doc_name, chat_history, question, modality) -> str:
    system_text = (
        "업로드된 문서를 분석하는 AI입니다. 한국어로 답하세요. "
        "문서의 표·이미지·차트 내용도 정확히 해석하여 답변하세요."
        if modality == "multimodal"
        else "업로드된 문서를 분석하는 AI입니다. 한국어로 답하세요."
    )
    resp = bedrock_rt.converse(
        modelId=GEN_MODEL_ID,
        system=[{"text": system_text}],
        messages=build_converse_messages(chat_history, question, pdf_bytes, doc_name),
        inferenceConfig={"maxTokens": 1024, "temperature": 0.3},
    )
    return resp["output"]["message"]["content"][0]["text"]


# ════════════════════════════════════════════════════════════════
# 세션 초기화
# ════════════════════════════════════════════════════════════════

for _k, _v in {
    "kb_messages": [], "kb_pending": None,
    "file_messages": [], "file_pdf_bytes": None,
    "file_doc_name": "", "file_modality": "", "file_uploaded_name": "",
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ════════════════════════════════════════════════════════════════
# 사이드바
# ════════════════════════════════════════════════════════════════

with st.sidebar:

    # ── 최상단: 모델 / 리전 (2줄, 약간 큰 글자) ───────────────
    st.markdown(f"""
<div class="sidebar-info">
  🤖 모델: <span>{GEN_MODEL_ID}</span><br>
  🌏 리전: <span>{REGION}</span>
</div>
""", unsafe_allow_html=True)

    # ── 모드 선택 라디오 ───────────────────────────────────────
    st.markdown("---")
    st.markdown("<p style='font-size:0.88rem; color:#aac4e0; margin-bottom:0.3rem;'>"
                "[ 선택 ]</p>", unsafe_allow_html=True)
    mode = st.radio(
        "챗봇 선택",
        options=["📚 KB 챗봇", "📄 파일 챗봇"],
        key="chat_mode",
        label_visibility="collapsed",
    )

    # ── KB 챗봇 세부 설정 ──────────────────────────────────────
    st.markdown("---")
    if mode == "📚 KB 챗봇":
        st.markdown("**📚 KB 챗봇 설정**")

        kb_opts = load_kb_ids()
        if not kb_opts or not any(kb_opts.values()):
            st.error("KB ID 없음. P3_03 실행 후 재시작")
            kb_ready = False
            kb_id = kb_label = ""
        else:
            kb_opts  = {k: v for k, v in kb_opts.items() if v}
            kb_label = st.selectbox("Knowledge Base", list(kb_opts.keys()),
                                    key="kb_select", label_visibility="collapsed")
            kb_id    = kb_opts[kb_label]
            kb_ready = True

            show_cit = st.checkbox("출처 표시", value=True, key="kb_citations")
            st.code(kb_id, language=None)
            st.markdown(
                f"[KB Console]({CONSOLE}/bedrock/home?region={REGION}"
                f"#/knowledge-bases/{kb_id})"
            )
            if st.button("💬 대화 초기화", key="kb_clear"):
                st.session_state.kb_messages = []
                st.rerun()

            st.markdown("**예시 질문**")
            for ex in [
                "5GX 요금제 월 요금이 얼마인가요?",
                "데이터 무제한 요금제 추천해 주세요.",
                "약정 없이 쓸 수 있는 요금제는?",
                "가장 저렴한 요금제와 데이터 용량은?",
                "5GX와 LTE 요금제 차이는?",
            ]:
                if st.button(ex, key=f"kb_ex_{ex[:10]}"):
                    st.session_state.kb_pending = ex
    else:
        kb_ready = False
        kb_id = kb_label = ""
        show_cit = False

    # ── 파일 챗봇 세부 설정 ────────────────────────────────────
    if mode == "📄 파일 챗봇":
        st.markdown("**📄 파일 챗봇 설정**")

        uploaded = st.file_uploader(
            "PDF 업로드", type=["pdf"], key="file_uploader",
            label_visibility="collapsed",
            help="최대 약 4.5MB (Bedrock document 블록 제한)",
        )
        if uploaded:
            pdf_bytes = uploaded.read()
            if uploaded.name != st.session_state.file_uploaded_name:
                st.session_state.file_pdf_bytes     = pdf_bytes
                st.session_state.file_doc_name      = safe_doc_name(uploaded.name)
                st.session_state.file_modality      = detect_modality(pdf_bytes)
                st.session_state.file_uploaded_name = uploaded.name
                st.session_state.file_messages      = []
            modality = st.session_state.file_modality
            badge    = "🖼️ 멀티모달" if modality == "multimodal" else "📝 텍스트"
            st.success(f"✅ {uploaded.name[:28]}")
            st.caption(f"{len(st.session_state.file_pdf_bytes)//1024} KB · {badge}")

        if st.button("💬 대화 초기화", key="file_clear"):
            st.session_state.file_messages = []
            st.rerun()

        if st.session_state.file_pdf_bytes:
            st.markdown("**예시 질문**")
            for sg in [
                "이 문서의 핵심 내용을 요약해줘.",
                "주요 수치나 데이터를 정리해줘.",
                "결론 또는 시사점은?",
                "목차 또는 섹션 구조를 알려줘.",
            ]:
                if st.button(sg, key=f"file_sg_{sg[:10]}"):
                    st.session_state["file_pending"] = sg


# ════════════════════════════════════════════════════════════════
# 메인 — 선택된 챗봇 단독 풀너비
# ════════════════════════════════════════════════════════════════

if mode == "📚 KB 챗봇":
    st.subheader("📚 Knowledge Base RAG 챗봇")
    if not kb_ready:
        st.info("사이드바에서 KB를 확인하세요.")
    else:
        st.caption(f"KB: {kb_label}  |  모델: {GEN_MODEL_ID}")

        for msg in st.session_state.kb_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if msg["role"] == "assistant" and show_cit and msg.get("citations"):
                    with st.expander(f"📎 출처 ({len(msg['citations'])}개)"):
                        for i, cit in enumerate(msg["citations"], 1):
                            for ref in cit.get("retrievedReferences", []):
                                uri  = ref.get("location", {}).get("s3Location", {}).get("uri", "")
                                text = ref.get("content", {}).get("text", "")[:200]
                                st.markdown(f"**[{i}]** `{uri}`")
                                st.caption(text + "...")

        user_input = st.session_state.kb_pending or st.chat_input("요금제에 대해 질문하세요...")
        st.session_state.kb_pending = None

        if user_input:
            st.session_state.kb_messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.write(user_input)
            with st.chat_message("assistant"):
                with st.spinner("KB 검색 중..."):
                    try:
                        answer, citations = kb_ask(kb_id, user_input)
                        st.write(answer)
                        if show_cit and citations:
                            with st.expander(f"📎 출처 ({len(citations)}개)"):
                                for i, cit in enumerate(citations, 1):
                                    for ref in cit.get("retrievedReferences", []):
                                        uri  = ref.get("location", {}).get("s3Location", {}).get("uri", "")
                                        text = ref.get("content", {}).get("text", "")[:200]
                                        st.markdown(f"**[{i}]** `{uri}`")
                                        st.caption(text + "...")
                        st.session_state.kb_messages.append({
                            "role": "assistant", "content": answer, "citations": citations
                        })
                    except Exception as e:
                        err = f"오류: {e}"
                        st.error(err)
                        st.session_state.kb_messages.append(
                            {"role": "assistant", "content": err, "citations": []}
                        )
            st.rerun()

else:  # 📄 파일 챗봇
    st.subheader("📄 파일 업로드 RAG 챗봇")
    if not st.session_state.file_pdf_bytes:
        st.info("👈 사이드바에서 PDF 파일을 업로드하세요.")
    else:
        modality  = st.session_state.file_modality
        doc_name  = st.session_state.file_doc_name
        pdf_bytes = st.session_state.file_pdf_bytes
        badge     = "🖼️ 멀티모달" if modality == "multimodal" else "📝 텍스트"
        st.caption(
            f"문서: `{st.session_state.file_uploaded_name}`  |  "
            f"유형: {badge}  |  모델: {GEN_MODEL_ID}"
        )

        for msg in st.session_state.file_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        pending    = st.session_state.pop("file_pending", None)
        user_input = pending or st.chat_input("업로드한 문서에 대해 질문하세요...")

        if user_input:
            st.session_state.file_messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.write(user_input)
            with st.chat_message("assistant"):
                with st.spinner("문서 분석 중..."):
                    try:
                        history = st.session_state.file_messages[:-1]
                        answer  = file_ask(pdf_bytes, doc_name, history, user_input, modality)
                        st.write(answer)
                        st.session_state.file_messages.append(
                            {"role": "assistant", "content": answer}
                        )
                    except Exception as e:
                        err = f"오류: {e}"
                        st.error(err)
                        st.session_state.file_messages.append(
                            {"role": "assistant", "content": err}
                        )
            st.rerun()
