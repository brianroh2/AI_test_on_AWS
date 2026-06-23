# ============================================================
# 파일명: P7_02_jarvis_streamlit.py
# 주제: 자비스 AI — 음성+텍스트 통합 Streamlit 챗봇
#
# 파이프라인 A (최적화):
#   Polly TTS → Strands Agent (Haiku) → Polly TTS
#
# 핵심 최적화:
#   - Claude Haiku 4.5 사용 (Sonnet 대비 10배 저렴, 음성 대화에 충분)
#   - 시스템 프롬프트: "3문장 이내" 강제 → 음성 청취 자연스러움
#   - Strands 도구(날씨/검색/계산) 통합
#   - 텍스트 + 음성 동시 응답 (브라우저 재생)
#
# 실행:
#   streamlit run P7_02_jarvis_streamlit.py \
#     --server.port 8512 --server.headless true &
#   접속: VS Code Ports 탭 → 8512 포워딩
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚠️  SageMaker 실행 역할 추가 권한 필요 (음성 기능 사용 시)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TTS(음성 응답) 토글을 켜면 Amazon Polly를 호출합니다.
# SageMaker 기본 실행 역할에는 Polly 권한이 없습니다.
# 권한 미설정 시 사이드바에 오류 메시지가 표시되며
# 텍스트 응답은 정상 동작합니다.
#
# 권한 추가 방법: docs/SageMaker_IAM_권한설정.md 참고
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ============================================================

import streamlit as st
import boto3
import base64
import requests
import io
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator

REGION        = "us-east-1"
HAIKU_ID      = "us.anthropic.claude-haiku-4-5-20251001"   # 음성 대화용 — 빠르고 경제적
SONNET_ID     = "global.anthropic.claude-sonnet-4-6"       # 고품질 응답용
POLLY_VOICE   = "Seoyeon"   # 한국어 Neural 음성

st.set_page_config(
    page_title="JARVIS AI",
    page_icon="🤖",
    layout="wide",
)


# ── Bedrock 모델 ─────────────────────────────────────────────
@st.cache_resource
def get_model(model_id: str):
    session = boto3.Session(region_name=REGION)
    return BedrockModel(
        model_id=model_id,
        boto_session=session,
        streaming=True,
    )


polly_client = boto3.client("polly", region_name=REGION)


# ── Polly TTS ─────────────────────────────────────────────────
def text_to_speech(text: str) -> bytes | None:
    try:
        import re
        clean = re.sub(r'[*_`#\[\]()]', '', text)
        clean = re.sub(r'https?://\S+', '', clean).strip()
        if not clean:
            return None
        resp = polly_client.synthesize_speech(
            Text=clean[:3000],
            OutputFormat="mp3",
            VoiceId=POLLY_VOICE,
            Engine="neural",
            LanguageCode="ko-KR",
        )
        return resp["AudioStream"].read()
    except Exception as e:
        err = str(e)
        if "AccessDenied" in err or "not authorized" in err:
            st.sidebar.error(
                "Polly 권한 없음\n\n"
                "IAM 역할에 `polly:SynthesizeSpeech` 권한을 추가하세요.\n"
                "자세한 내용은 P7_01_jarvis_stt_tts.py 실행 참조."
            )
        else:
            st.sidebar.warning(f"TTS 오류: {e}")
        return None


def autoplay_audio(audio_bytes: bytes):
    b64 = base64.b64encode(audio_bytes).decode()
    audio_html = f"""
    <audio autoplay style="display:none;">
      <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
    </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)


# ── 자비스 도구 ───────────────────────────────────────────────
@tool
def weather_forecast(city: str) -> str:
    """지정한 도시의 현재 날씨를 조회한다.

    Args:
        city: 날씨를 조회할 도시 이름 (영문). 예: Seoul, Tokyo, London
    """
    try:
        resp = requests.get(f"https://wttr.in/{city}?format=j1", timeout=5)
        resp.raise_for_status()
        cc = resp.json()["current_condition"][0]
        return (
            f"{city}: {cc['weatherDesc'][0]['value']}, "
            f"{cc['temp_C']}°C, 습도 {cc['humidity']}%"
        )
    except Exception as e:
        return f"날씨 조회 실패 ({city}): {e}"


@tool
def web_search(query: str, max_results: int = 3) -> str:
    """DuckDuckGo로 웹 검색을 수행한다.

    Args:
        query: 검색할 키워드 또는 문장
        max_results: 반환할 최대 결과 수 (기본값 3)
    """
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return f"'{query}' 검색 결과 없음"
        return "\n".join(
            f"{i+1}. {r['title']} — {r['href']}" for i, r in enumerate(results)
        )
    except Exception as e:
        return f"검색 실패: {e}"


# ── 자비스 시스템 프롬프트 ─────────────────────────────────────
JARVIS_SYSTEM = """당신은 'JARVIS'입니다. 사용자의 개인 AI 음성 비서입니다.

## 응답 원칙
- **반드시 3문장 이내**로 간결하게 답변합니다. (음성 청취 최적화)
- 친근하고 명확한 한국어를 사용합니다.
- 도구가 있으면 적극 활용하여 정확한 정보를 제공합니다.
- 계산이 필요하면 반드시 calculator 도구를 사용합니다.
- 마크다운 헤더(#, ##)나 긴 목록은 사용하지 않습니다.

## 도구 사용
- 날씨 질문 → weather_forecast
- 검색 필요 → web_search
- 계산 필요 → calculator
"""


# ── 세션 상태 초기화 ──────────────────────────────────────────
def init_state():
    defaults = {
        "messages":    [],
        "voice_on":    True,
        "model_key":   "haiku",
        "token_total": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='background:#1a1a2e;border-radius:8px;padding:0.8rem 1rem;"
        "font-size:1rem;color:#e0e0e0;text-align:center;'>"
        "🤖 <b style='font-size:1.2rem;color:#7ec8e3;'>JARVIS</b><br>"
        "<span style='font-size:0.8rem;color:#aaa;'>Personal AI Assistant</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # 모델 선택
    model_choice = st.radio(
        "🧠 모델 선택",
        options=["haiku", "sonnet"],
        format_func=lambda x: {
            "haiku":  "⚡ Haiku (빠름·경제적, 음성 권장)",
            "sonnet": "💎 Sonnet (고품질·느림)",
        }[x],
        index=0,
        help="음성 대화에는 Haiku가 최적입니다.",
    )
    st.session_state["model_key"] = model_choice

    st.markdown("---")

    # 음성 응답 토글
    st.session_state["voice_on"] = st.toggle(
        "🔊 음성 응답 (TTS)",
        value=st.session_state["voice_on"],
        help="Polly Neural TTS로 응답을 자동 재생합니다.",
    )

    st.markdown("---")

    # 빠른 명령
    st.markdown("**⚡ 빠른 명령**")
    quick_cmds = [
        "서울 지금 날씨 알려줘",
        "내일 도쿄 날씨는?",
        "1234 × 5678 계산해줘",
        "AWS Bedrock 최신 소식 검색해줘",
        "런던과 파리 기온 평균 계산해줘",
    ]
    for cmd in quick_cmds:
        if st.button(cmd, key=f"q_{cmd[:8]}", use_container_width=True):
            st.session_state["pending"] = cmd

    st.markdown("---")

    # 토큰 / 대화 정보
    st.markdown(f"**📊 통계**")
    st.metric("대화 수", len([m for m in st.session_state.messages if m["role"] == "user"]))

    if st.button("🗑 대화 초기화", use_container_width=True):
        st.session_state["messages"]    = []
        st.session_state["token_total"] = 0
        st.rerun()


# ── 메인 ─────────────────────────────────────────────────────
st.markdown(
    "<h1 style='text-align:center;color:#7ec8e3;'>🤖 JARVIS</h1>"
    "<p style='text-align:center;color:#aaa;font-size:0.9rem;'>"
    "Amazon Bedrock + Strands Agent + Amazon Polly</p>",
    unsafe_allow_html=True,
)

model_id  = HAIKU_ID if st.session_state["model_key"] == "haiku" else SONNET_ID
voice_str = "ON 🔊" if st.session_state["voice_on"] else "OFF 🔇"
st.caption(f"모델: `{model_id.split('.')[-1]}` | 음성: {voice_str}")

# 기존 대화 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# pending 처리 (빠른 명령 버튼)
if "pending" not in st.session_state:
    st.session_state["pending"] = ""

user_input = st.session_state.get("pending") or st.chat_input("자비스에게 말씀하세요...")
st.session_state["pending"] = ""

# ── 응답 생성 ─────────────────────────────────────────────────
if user_input and user_input.strip():
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        audio_placeholder    = st.empty()
        full_response        = ""

        model  = get_model(model_id)
        agent  = Agent(
            model=model,
            tools=[weather_forecast, web_search, calculator],
            system_prompt=JARVIS_SYSTEM,
            callback_handler=None,
        )

        with st.spinner("JARVIS 처리 중..."):
            result        = agent(user_input)
            full_response = str(result).strip()

        response_placeholder.markdown(full_response)

        # TTS 재생
        if st.session_state["voice_on"]:
            audio = text_to_speech(full_response)
            if audio:
                with audio_placeholder:
                    autoplay_audio(audio)
                    # 다운로드 버튼도 제공
                    st.download_button(
                        "💾 음성 저장",
                        data=audio,
                        file_name="jarvis_response.mp3",
                        mime="audio/mp3",
                        key=f"dl_{len(st.session_state.messages)}",
                    )

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    st.rerun()
