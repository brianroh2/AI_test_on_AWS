"""
P3_07_rag_chatbot.py
────────────────────────────────────────────────────────────────────
RAG 챕터 07 — Streamlit RAG 챗봇

자동 처리:  rag_config.json 에서 KB ID 자동 로드
사용자 필요: 없음 (09 완료 후 바로 실행)

실행:
  streamlit run P3_07_rag_chatbot.py --server.port 8503 --server.headless true &
  접속: VS Code Ports 탭 → 8503 포워딩
────────────────────────────────────────────────────────────────────
"""

import boto3
import json
import streamlit as st
from pathlib import Path

REGION  = "us-east-1"
CONSOLE = f"https://{REGION}.console.aws.amazon.com"

CONFIG_FILE   = Path(__file__).parent / "rag_config.json"
GEN_MODEL_ID  = "us.anthropic.claude-sonnet-4-6"
_ACCOUNT_ID   = boto3.client("sts").get_caller_identity()["Account"]
GEN_MODEL_ARN = f"arn:aws:bedrock:{REGION}:{_ACCOUNT_ID}:inference-profile/{GEN_MODEL_ID}"

agent_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)

st.set_page_config(
    page_title="통신사 요금제 RAG 챗봇",
    page_icon="📡",
    layout="wide",
)


# ── KB ID 로드 ────────────────────────────────────────────────
@st.cache_data
def load_kb_ids() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
        return {
            "텍스트 KB (Titan Embeddings)":    cfg.get("text_kb_id", ""),
            "멀티모달 KB (Nova Embeddings)":   cfg.get("multimodal_kb_id", ""),
        }
    except Exception:
        return {}


# ── RAG 질의 ─────────────────────────────────────────────────
def rag_ask(kb_id: str, question: str) -> tuple[str, list]:
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


# ════════════════════════════════════════════════════════════════
# 사이드바
# ════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("📡 RAG 챗봇 설정")
    st.markdown("---")

    kb_opts = load_kb_ids()

    if not kb_opts or not any(kb_opts.values()):
        st.error(
            "KB ID가 없습니다.\n\n"
            "**P3_03_rag_kb_create.py** 를 실행하여 "
            "rag_config.json을 생성하세요."
        )
        st.stop()

    # 빈 ID 제거
    kb_opts = {k: v for k, v in kb_opts.items() if v}

    selected_label = st.selectbox("Knowledge Base 선택", list(kb_opts.keys()))
    selected_kb_id = kb_opts[selected_label]

    show_citations = st.checkbox("출처(citations) 표시", value=True)

    st.markdown("---")
    st.markdown("**선택된 KB ID**")
    st.code(selected_kb_id)
    st.markdown(
        f"[Console에서 KB 확인]"
        f"({CONSOLE}/bedrock/home?region={REGION}#/knowledge-bases/{selected_kb_id})"
    )
    st.markdown(
        f"[OpenSearch 컬렉션 확인]"
        f"({CONSOLE}/aos/home?region={REGION}#/collections)"
    )

    st.markdown("---")
    if st.button("대화 초기화"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.markdown("**예시 질문**")
    examples = [
        "5GX 요금제 월 요금이 얼마인가요?",
        "데이터 무제한 요금제 추천해 주세요.",
        "약정 없이 쓸 수 있는 요금제는?",
        "가장 저렴한 요금제와 데이터 용량은?",
        "5GX와 LTE 요금제 차이는?",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex[:12]}"):
            st.session_state.pending = ex


# ════════════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════════════
st.title("📡 통신사 요금제 RAG 챗봇")
st.caption(f"Knowledge Base: {selected_label}  |  모델: {GEN_MODEL_ID}")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = None

# 기존 대화 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant" and show_citations and msg.get("citations"):
            with st.expander(f"📎 출처 ({len(msg['citations'])}개)"):
                for i, cit in enumerate(msg["citations"], 1):
                    for ref in cit.get("retrievedReferences", []):
                        uri  = ref.get("location", {}).get("s3Location", {}).get("uri", "")
                        text = ref.get("content", {}).get("text", "")[:200]
                        st.markdown(f"**[{i}]** `{uri}`")
                        st.caption(text + "...")

# 입력 처리
user_input = st.session_state.pending or st.chat_input("요금제에 대해 질문하세요...")
st.session_state.pending = None

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("KB 검색 중..."):
            try:
                answer, citations = rag_ask(selected_kb_id, user_input)
                st.write(answer)
                if show_citations and citations:
                    with st.expander(f"📎 출처 ({len(citations)}개)"):
                        for i, cit in enumerate(citations, 1):
                            for ref in cit.get("retrievedReferences", []):
                                uri  = ref.get("location", {}).get("s3Location", {}).get("uri", "")
                                text = ref.get("content", {}).get("text", "")[:200]
                                st.markdown(f"**[{i}]** `{uri}`")
                                st.caption(text + "...")
                st.session_state.messages.append({
                    "role": "assistant", "content": answer, "citations": citations
                })
            except Exception as e:
                err = f"오류: {e}"
                st.error(err)
                st.session_state.messages.append({
                    "role": "assistant", "content": err, "citations": []
                })
