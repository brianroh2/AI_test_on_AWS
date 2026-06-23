# ============================================================
# 파일명: P2_06_chatbot_streamlit.py
# 주제: Amazon Bedrock API + Streamlit 챗봇
#
# 【구성】
#   - SDK 선택: boto3 / Anthropic SDK / OpenAI(bedrock-mantle) 방식
#   - 실시간 스트리밍 응답
#   - 멀티턴 대화 히스토리 유지
#   - 토큰 통계: 마지막 호출 / SDK별 누적 / 전체 누적
#
# ============================================================
# 【SageMaker Code Editor 실행 및 접속 방법】
#
# ※ AWS 프록시 URL(/codeeditor/default/proxy/8501/)은
#   세션 토큰 만료 시 "Invalid or Expired Auth Token" 오류가
#   발생하므로 절대 사용하지 말 것.
#
# Step 1. 터미널에서 서버 실행
#   cd /home/sagemaker-user/vscode_project
#   streamlit run P2_06_chatbot_streamlit.py --server.port 8501 --server.headless true &
#
# Step 2. VS Code Ports 탭으로 접속 (토큰 만료 영향 없음)
#   - VS Code 하단 터미널 패널 → [Ports] 탭 클릭
#   - [Forward a Port] 클릭 → 8501 입력 → Enter
#   - 자동 생성된 https://...devtunnels.ms/... URL 클릭
#
# 【서버 종료】
#   - 브라우저 탭만 닫은 경우: 서버는 유지됨 → Ports 탭 재포워딩으로 재접속 가능
#   - 코드 수정 후 재시작 필요 시에만 kill:
#     kill $(ps aux | grep streamlit | grep -v grep | awk '{print $2}')
#   - Space Stop 시: 자동 종료됨 (수동 kill 불필요)
# ============================================================

import streamlit as st
import boto3
from anthropic import AnthropicBedrock

# ── 공통 설정 ─────────────────────────────────────────────
REGION = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"
DEFAULT_SYSTEM = "당신은 친절하고 유능한 AI 어시스턴트입니다. 한국어로 답변하세요."

SDK_KEYS = ["boto3", "Anthropic SDK", "OpenAI 방식"]
SDK_LABELS = {
    "boto3":        "boto3 (bedrock-runtime)",
    "Anthropic SDK":"Anthropic SDK",
    "OpenAI 방식":  "OpenAI SDK (bedrock-mantle 방식)",
}

# ── 페이지 설정 ────────────────────────────────────────────
st.set_page_config(page_title="Bedrock 챗봇", page_icon="🤖", layout="wide")


# ── 세션 상태 초기화 (앱 최초 로드 시 1회) ────────────────
def _init_state():
    defaults = {
        "messages": [],
        # SDK별 독립 카운터
        "sdk_stats": {k: {"calls": 0, "input": 0, "output": 0} for k in SDK_KEYS},
        # 마지막 호출 정보
        "last_call": {"sdk": "-", "input": 0, "output": 0},
        # 임시 저장소 (generator → 메인 루프 전달용)
        "_last_input_tokens": 0,
        "_last_output_tokens": 0,
        "_last_sdk_key": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ═══════════════════════════════════════════════════════════
# SDK별 스트리밍 함수 (generator)
# ═══════════════════════════════════════════════════════════

def stream_boto3(messages, system, max_tok, temp):
    """boto3 bedrock-runtime converse_stream"""
    bedrock = boto3.client("bedrock-runtime", region_name=REGION)
    boto3_msgs = [
        {"role": m["role"], "content": [{"text": m["content"]}]}
        for m in messages
    ]
    stream = bedrock.converse_stream(
        modelId=MODEL_ID,
        system=[{"text": system}],
        messages=boto3_msgs,
        inferenceConfig={"maxTokens": max_tok, "temperature": temp},
    )
    in_tok = out_tok = 0
    for event in stream["stream"]:
        if "contentBlockDelta" in event:
            yield event["contentBlockDelta"]["delta"]["text"]
        elif "metadata" in event:
            u = event["metadata"].get("usage", {})
            in_tok, out_tok = u.get("inputTokens", 0), u.get("outputTokens", 0)
    st.session_state._last_input_tokens = in_tok
    st.session_state._last_output_tokens = out_tok
    st.session_state._last_sdk_key = "boto3"


def stream_anthropic(messages, system, max_tok, temp):
    """Anthropic SDK (AnthropicBedrock) 스트리밍"""
    client = AnthropicBedrock(aws_region=REGION)
    sdk_msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
    with client.messages.stream(
        model=MODEL_ID, max_tokens=max_tok, temperature=temp,
        system=system, messages=sdk_msgs,
    ) as stream:
        for chunk in stream.text_stream:
            yield chunk
        final = stream.get_final_message()
        st.session_state._last_input_tokens = final.usage.input_tokens
        st.session_state._last_output_tokens = final.usage.output_tokens
    st.session_state._last_sdk_key = "Anthropic SDK"


def stream_openai_bedrock(messages, system, max_tok, temp):
    """
    OpenAI SDK 방식으로 Bedrock 호출 (bedrock-mantle 패턴)
    - OpenAI: system을 messages[0]으로 배치, content는 문자열
    - 내부에서 Bedrock Converse 형식으로 변환 후 boto3로 호출
    """
    bedrock = boto3.client("bedrock-runtime", region_name=REGION)
    # OpenAI 방식: system → messages 첫 번째 항목
    openai_msgs = [{"role": "system", "content": system}] + messages
    # Bedrock 형식으로 변환
    sys_text, bedrock_msgs = "", []
    for m in openai_msgs:
        if m["role"] == "system":
            sys_text = m["content"]
        else:
            bedrock_msgs.append({"role": m["role"], "content": [{"text": m["content"]}]})
    stream = bedrock.converse_stream(
        modelId=MODEL_ID,
        system=[{"text": sys_text}],
        messages=bedrock_msgs,
        inferenceConfig={"maxTokens": max_tok, "temperature": temp},
    )
    in_tok = out_tok = 0
    for event in stream["stream"]:
        if "contentBlockDelta" in event:
            yield event["contentBlockDelta"]["delta"]["text"]
        elif "metadata" in event:
            u = event["metadata"].get("usage", {})
            in_tok, out_tok = u.get("inputTokens", 0), u.get("outputTokens", 0)
    st.session_state._last_input_tokens = in_tok
    st.session_state._last_output_tokens = out_tok
    st.session_state._last_sdk_key = "OpenAI 방식"


STREAM_FUNCS = {
    "boto3":         stream_boto3,
    "Anthropic SDK": stream_anthropic,
    "OpenAI 방식":   stream_openai_bedrock,
}


# ═══════════════════════════════════════════════════════════
# 사이드바
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.header("⚙️ 설정")

    # SDK 선택
    sdk_key = st.radio(
        "호출 방식 선택",
        options=SDK_KEYS,
        format_func=lambda k: SDK_LABELS[k],
        index=0,
        help="boto3: AWS 네이티브 | Anthropic SDK: Claude 전용 | OpenAI 방식: OpenAI 호환",
    )

    st.divider()

    system_prompt = st.text_area(
        "시스템 프롬프트", value=DEFAULT_SYSTEM, height=110,
        help="모델의 역할·규칙을 설정합니다.",
    )
    max_tokens  = st.slider("최대 토큰 수",  100, 4096, 1024, 100)
    temperature = st.slider("Temperature",   0.0,  1.0,  0.7, 0.05)

    st.divider()

    # ── 토큰 통계 패널 ──────────────────────────────────────
    st.subheader("📊 토큰 사용량")

    # 1) 마지막 호출 (가장 최근 응답 1회)
    lc = st.session_state.last_call
    st.caption("**마지막 호출**")
    c1, c2, c3 = st.columns(3)
    c1.metric("SDK", lc["sdk"] if lc["sdk"] != "-" else "-")
    c2.metric("입력", lc["input"])
    c3.metric("출력", lc["output"])

    st.divider()

    # 2) 현재 선택된 SDK 누적
    cur = st.session_state.sdk_stats[sdk_key]
    st.caption(f"**현재 SDK 누적** ({SDK_LABELS[sdk_key]})")
    c1, c2, c3 = st.columns(3)
    c1.metric("호출 수",  cur["calls"])
    c2.metric("입력 합계", cur["input"])
    c3.metric("출력 합계", cur["output"])

    st.divider()

    # 3) SDK별 전체 누적 테이블
    st.caption("**SDK별 누적 비교**")
    rows = []
    for k in SDK_KEYS:
        s = st.session_state.sdk_stats[k]
        rows.append({
            "SDK":   k,
            "호출":  s["calls"],
            "입력":  s["input"],
            "출력":  s["output"],
            "합계":  s["input"] + s["output"],
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()

    # 대화 초기화 (SDK별 통계는 유지, 대화만 리셋)
    col_a, col_b = st.columns(2)
    if col_a.button("💬 대화 초기화", use_container_width=True,
                    help="대화 히스토리만 지웁니다. SDK 통계는 유지됩니다."):
        st.session_state.messages = []
        st.rerun()

    if col_b.button("📊 통계 초기화", use_container_width=True,
                    help="SDK별 토큰 통계를 모두 0으로 초기화합니다."):
        st.session_state.sdk_stats = {k: {"calls": 0, "input": 0, "output": 0} for k in SDK_KEYS}
        st.session_state.last_call = {"sdk": "-", "input": 0, "output": 0}
        st.rerun()


# ═══════════════════════════════════════════════════════════
# 메인: 대화 화면
# ═══════════════════════════════════════════════════════════
st.title("🤖 Amazon Bedrock 챗봇")
st.caption(f"현재 모드: **{SDK_LABELS[sdk_key]}** | 모델: `{MODEL_ID}`")

# 기존 대화 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 사용자 입력
if prompt := st.chat_input("메시지를 입력하세요..."):

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 스트리밍 응답
    with st.chat_message("assistant"):
        full_response = st.write_stream(
            STREAM_FUNCS[sdk_key](
                st.session_state.messages,
                system_prompt,
                max_tokens,
                temperature,
            )
        )

    # 응답 히스토리 추가
    st.session_state.messages.append({"role": "assistant", "content": full_response})

    # ── 토큰 통계 업데이트 ──────────────────────────────────
    in_tok  = st.session_state._last_input_tokens
    out_tok = st.session_state._last_output_tokens
    used_sdk = st.session_state._last_sdk_key  # 실제 사용된 SDK 키

    # 마지막 호출 기록
    st.session_state.last_call = {
        "sdk":    used_sdk,
        "input":  in_tok,
        "output": out_tok,
    }

    # SDK별 누적
    st.session_state.sdk_stats[used_sdk]["calls"]  += 1
    st.session_state.sdk_stats[used_sdk]["input"]  += in_tok
    st.session_state.sdk_stats[used_sdk]["output"] += out_tok

    st.rerun()
