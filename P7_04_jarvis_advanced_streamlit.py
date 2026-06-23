# ============================================================
# 파일명: P7_04_jarvis_advanced_streamlit.py
# 주제: JARVIS AI 고도화 — 대화/RAG/다국어/통역/YouTube
#
# [탭 1] 자비스 대화
#   - 파일 업로드 → 문서 RAG (InlineDocumentSource)
#   - 문서에 없으면 자동 웹검색 보완
#   - 날씨/계산/시간 도구 자동 호출
#   - 다국어 음성 (한국어/영어/일본어/중국어/프랑스어/스페인어/독일어)
#   - 음성 속도 조절
#   - 모드: 음성+텍스트 / 음성전용
#   - 통역 모드: 입력 언어 → 출력 언어 변환 + 음성 안내
#
# [탭 2] YouTube
#   - URL 입력 → 자막 추출 → Claude 요약 → Polly 음성 안내
#   - 영상 임베드 재생
#   - 키워드 검색 → YouTube 링크 제공
#
# 실행:
#   streamlit run P7_04_jarvis_advanced_streamlit.py \
#     --server.port 8514 --server.headless true &
#   접속: VS Code Ports 탭 → 8514 포워딩
#
# ⚠️  SageMaker IAM 권한 필요 (음성 기능):
#   polly:SynthesizeSpeech — docs/SageMaker_IAM_권한설정.md 참고
# ============================================================

import re
import base64
import textwrap
import streamlit as st
import boto3
import requests
import pdfplumber
import io
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator, current_time

REGION      = "us-east-1"
HAIKU_ID    = "us.anthropic.claude-haiku-4-5-20251001"
SONNET_ID   = "global.anthropic.claude-sonnet-4-6"

# ── Polly 언어/음성 매핑 ──────────────────────────────────────
VOICE_OPTIONS = {
    "한국어":    {"VoiceId": "Seoyeon",  "LanguageCode": "ko-KR",  "flag": "🇰🇷"},
    "영어(미국)": {"VoiceId": "Joanna",   "LanguageCode": "en-US",  "flag": "🇺🇸"},
    "영어(영국)": {"VoiceId": "Amy",      "LanguageCode": "en-GB",  "flag": "🇬🇧"},
    "일본어":    {"VoiceId": "Kazuha",   "LanguageCode": "ja-JP",  "flag": "🇯🇵"},
    "중국어":    {"VoiceId": "Zhiyu",    "LanguageCode": "cmn-CN", "flag": "🇨🇳"},
    "프랑스어":  {"VoiceId": "Lea",      "LanguageCode": "fr-FR",  "flag": "🇫🇷"},
    "스페인어":  {"VoiceId": "Lucia",    "LanguageCode": "es-ES",  "flag": "🇪🇸"},
    "독일어":    {"VoiceId": "Vicki",    "LanguageCode": "de-DE",  "flag": "🇩🇪"},
}

SPEED_MAP = {"느림": "slow", "보통": "medium", "빠름": "fast"}

st.set_page_config(page_title="JARVIS Advanced", page_icon="🤖", layout="wide")


# ── Bedrock 모델 캐시 ─────────────────────────────────────────
@st.cache_resource
def get_model(model_id: str):
    return BedrockModel(
        model_id=model_id,
        boto_session=boto3.Session(region_name=REGION),
        streaming=False,
    )

polly_client = boto3.client("polly", region_name=REGION)
bedrock      = boto3.client("bedrock-runtime", region_name=REGION)


# ── TTS 함수 ──────────────────────────────────────────────────
def text_to_speech(text: str, lang_key: str, speed: str) -> bytes | None:
    try:
        v     = VOICE_OPTIONS[lang_key]
        clean = re.sub(r'[*_`#\[\]<>]', '', text)
        clean = re.sub(r'https?://\S+', '', clean).strip()
        if not clean:
            return None
        rate  = SPEED_MAP.get(speed, "medium")
        ssml  = f'<speak><prosody rate="{rate}">{clean[:2900]}</prosody></speak>'
        resp  = polly_client.synthesize_speech(
            Text=ssml, TextType="ssml",
            OutputFormat="mp3",
            VoiceId=v["VoiceId"],
            Engine="neural",
            LanguageCode=v["LanguageCode"],
        )
        return resp["AudioStream"].read()
    except Exception as e:
        err = str(e)
        if "AccessDenied" in err or "not authorized" in err:
            st.sidebar.error("Polly 권한 없음\ndocs/SageMaker_IAM_권한설정.md 참고")
        else:
            st.sidebar.warning(f"TTS 오류: {e}")
        return None


def autoplay_audio(audio_bytes: bytes, key: str):
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(
        f'<audio autoplay style="width:100%;margin-top:4px;">'
        f'<source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>',
        unsafe_allow_html=True,
    )
    st.download_button("💾 음성 저장", audio_bytes,
                       file_name="jarvis.mp3", mime="audio/mp3", key=f"dl_{key}")


# ── PDF 텍스트 추출 ───────────────────────────────────────────
def extract_text_from_file(uploaded) -> str:
    name = uploaded.name.lower()
    try:
        if name.endswith(".pdf"):
            text = []
            with pdfplumber.open(io.BytesIO(uploaded.read())) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text.append(t)
            return "\n".join(text)[:12000]
        else:
            return uploaded.read().decode("utf-8", errors="ignore")[:12000]
    except Exception as e:
        return f"파일 읽기 오류: {e}"


# ── Strands 도구 정의 ─────────────────────────────────────────
@tool
def weather_forecast(city: str) -> str:
    """지정한 도시의 현재 날씨를 조회한다.
    Args:
        city: 날씨를 조회할 도시 이름 (영문). 예: Seoul, Tokyo
    """
    try:
        r  = requests.get(f"https://wttr.in/{city}?format=j1", timeout=5)
        cc = r.json()["current_condition"][0]
        return (f"{city}: {cc['weatherDesc'][0]['value']}, "
                f"{cc['temp_C']}°C, 습도 {cc['humidity']}%")
    except Exception as e:
        return f"날씨 조회 실패: {e}"


@tool
def web_search(query: str, max_results: int = 4) -> str:
    """DuckDuckGo로 웹 검색한다. 문서에 없는 최신 정보 조회에 사용.
    Args:
        query: 검색 키워드
        max_results: 결과 수 (기본 4)
    """
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return f"'{query}' 검색 결과 없음"
        return "\n".join(f"{i+1}. {r['title']}\n   {r['body'][:150]}\n   {r['href']}"
                         for i, r in enumerate(results))
    except Exception as e:
        return f"검색 실패: {e}"


@tool
def youtube_search(query: str, max_results: int = 3) -> str:
    """YouTube 영상을 검색하여 제목과 URL을 반환한다.
    Args:
        query: 검색어
        max_results: 결과 수 (기본 3)
    """
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(f"site:youtube.com {query}", max_results=max_results)
        if not results:
            return "YouTube 검색 결과 없음"
        lines = []
        for r in results:
            href = r.get("href", "")
            if "youtube.com/watch" in href or "youtu.be" in href:
                lines.append(f"- {r['title']}\n  {href}")
        return "\n".join(lines) if lines else "YouTube 링크를 찾지 못했습니다."
    except Exception as e:
        return f"YouTube 검색 실패: {e}"


# ── YouTube 자막 추출 ─────────────────────────────────────────
def extract_video_id(url: str) -> str | None:
    patterns = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def get_transcript(video_id: str) -> tuple[str, str]:
    """자막 텍스트와 언어 코드 반환. 실패 시 ("", "") 반환."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
        # 한국어 우선, 없으면 영어, 없으면 자동생성 포함 첫 번째
        for lang in [["ko"], ["en"], None]:
            try:
                if lang:
                    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=lang)
                else:
                    transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
                    transcript  = transcripts.find_transcript(
                        [t.language_code for t in transcripts]
                    ).fetch()
                text = " ".join(t["text"] for t in transcript)
                return text[:8000], (lang[0] if lang else "auto")
            except Exception:
                continue
        return "", ""
    except Exception:
        return "", ""


# ── RAG + 웹검색 통합 응답 ────────────────────────────────────
def build_rag_context(question: str, doc_texts: list[str]) -> str:
    """업로드 문서에서 관련 청크 추출 (단순 키워드 매칭)."""
    if not doc_texts:
        return ""
    keywords = set(question.replace("?", "").replace(".", "").split())
    scored = []
    for doc in doc_texts:
        chunks = [doc[i:i+500] for i in range(0, len(doc), 400)]
        for chunk in chunks:
            score = sum(1 for kw in keywords if kw in chunk)
            if score > 0:
                scored.append((score, chunk))
    scored.sort(reverse=True)
    top = [c for _, c in scored[:4]]
    return "\n---\n".join(top) if top else ""


JARVIS_SYSTEM = """당신은 'JARVIS'입니다. 사용자의 개인 AI 음성+텍스트 비서입니다.

## 응답 원칙
- 음성으로도 전달되므로 **3~5문장 이내**로 간결하게 답변합니다.
- 문서 컨텍스트가 제공되면 해당 내용을 우선 활용합니다.
- 문서에 없는 내용은 web_search 도구로 보완합니다.
- 날씨·시간·계산은 해당 도구를 반드시 사용합니다.
- 마크다운 헤더(#)와 과도한 목록은 지양합니다.
"""

TRANSLATE_SYSTEM = """당신은 전문 통역사입니다.
입력 텍스트를 지정된 언어로 자연스럽게 번역하세요.
번역 결과 텍스트만 출력하고 설명이나 부연은 하지 마세요.
"""


# ── 세션 상태 초기화 ──────────────────────────────────────────
def init():
    defaults = {
        "messages": [], "doc_texts": [], "doc_names": [],
        "voice_on": True, "voice_only": False,
        "lang_key": "한국어", "speed": "보통",
        "translate_mode": False, "src_lang": "한국어", "tgt_lang": "영어(미국)",
        "model_key": "haiku", "pending": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init()


# ════════════════════════════════════════════════════════════
# 사이드바
# ════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        "<div style='background:#0d1b2a;border-radius:8px;padding:0.8rem 1rem;"
        "text-align:center;margin-bottom:0.5rem;'>"
        "<span style='font-size:1.4rem;'>🤖</span><br>"
        "<b style='color:#7ec8e3;font-size:1.1rem;'>JARVIS Advanced</b><br>"
        "<span style='color:#aaa;font-size:0.8rem;'>AI 음성+텍스트 비서</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── 모델 선택 ──
    st.markdown("**🧠 모델**")
    st.session_state["model_key"] = st.radio(
        "모델", ["haiku", "sonnet"],
        format_func=lambda x: "⚡ Haiku (빠름·경제적)" if x == "haiku" else "💎 Sonnet (고품질)",
        index=0, label_visibility="collapsed",
    )

    st.markdown("---")

    # ── 음성 설정 ──
    st.markdown("**🔊 음성 설정**")
    st.session_state["voice_on"] = st.toggle("음성 응답 ON/OFF", value=st.session_state["voice_on"])

    lang_labels = [f"{v['flag']} {k}" for k, v in VOICE_OPTIONS.items()]
    lang_keys   = list(VOICE_OPTIONS.keys())
    cur_idx     = lang_keys.index(st.session_state["lang_key"])
    selected    = st.selectbox("언어 / 음성", lang_labels, index=cur_idx)
    st.session_state["lang_key"] = lang_keys[lang_labels.index(selected)]

    st.session_state["speed"] = st.select_slider(
        "말하기 속도", options=["느림", "보통", "빠름"],
        value=st.session_state["speed"],
    )

    st.markdown("---")

    # ── 표시 모드 ──
    st.markdown("**📺 표시 모드**")
    mode = st.radio("모드", ["음성+텍스트", "음성전용"],
                    index=1 if st.session_state["voice_only"] else 0,
                    label_visibility="collapsed")
    st.session_state["voice_only"] = (mode == "음성전용")

    st.markdown("---")

    # ── 통역 모드 ──
    st.session_state["translate_mode"] = st.toggle(
        "🌐 통역 모드", value=st.session_state["translate_mode"]
    )
    if st.session_state["translate_mode"]:
        src_idx = lang_keys.index(st.session_state["src_lang"])
        tgt_idx = lang_keys.index(st.session_state["tgt_lang"])
        st.session_state["src_lang"] = lang_keys[
            lang_labels.index(st.selectbox("입력 언어", lang_labels, index=src_idx, key="src"))
        ]
        st.session_state["tgt_lang"] = lang_keys[
            lang_labels.index(st.selectbox("출력 언어", lang_labels, index=tgt_idx, key="tgt"))
        ]

    st.markdown("---")

    # ── 파일 업로드 ──
    st.markdown("**📎 문서 업로드 (RAG)**")
    uploaded_files = st.file_uploader(
        "PDF / TXT", type=["pdf", "txt"],
        accept_multiple_files=True, label_visibility="collapsed",
    )
    if uploaded_files:
        new_names = [f.name for f in uploaded_files]
        if new_names != st.session_state["doc_names"]:
            st.session_state["doc_texts"] = [extract_text_from_file(f) for f in uploaded_files]
            st.session_state["doc_names"] = new_names
        for n in st.session_state["doc_names"]:
            st.caption(f"📄 {n}")
    else:
        st.session_state["doc_texts"] = []
        st.session_state["doc_names"] = []

    st.markdown("---")

    # ── 빠른 명령 ──
    st.markdown("**⚡ 빠른 명령**")
    for cmd in ["서울 지금 날씨", "오늘 AI 뉴스 검색", "1234 × 5678 계산", "지금 몇 시야?"]:
        if st.button(cmd, key=f"q_{cmd[:6]}", use_container_width=True):
            st.session_state["pending"] = cmd

    if st.button("🗑 대화 초기화", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()


# ════════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════════
st.markdown(
    "<h1 style='text-align:center;color:#7ec8e3;margin-bottom:0;'>🤖 JARVIS Advanced</h1>"
    "<p style='text-align:center;color:#888;font-size:0.85rem;margin-top:4px;'>"
    "문서 RAG · 웹검색 · 다국어 · 통역 · YouTube</p>",
    unsafe_allow_html=True,
)

tab_chat, tab_youtube = st.tabs(["💬 자비스 대화", "▶ YouTube"])


# ════════════════════════════════════════════════════════════
# 탭 1: 자비스 대화
# ════════════════════════════════════════════════════════════
with tab_chat:
    voice_only = st.session_state["voice_only"]

    # 기존 대화 출력 (음성전용 모드에서는 최신 1개만)
    msgs = st.session_state["messages"]
    show_msgs = msgs[-1:] if voice_only and msgs else msgs
    for msg in show_msgs:
        if not voice_only:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("source"):
                    st.caption(f"출처: {msg['source']}")

    user_input = st.session_state.get("pending") or st.chat_input("자비스에게 말씀하세요...")
    st.session_state["pending"] = ""

    if user_input and user_input.strip():
        q = user_input.strip()

        # 통역 모드
        if st.session_state["translate_mode"]:
            src = st.session_state["src_lang"]
            tgt = st.session_state["tgt_lang"]
            translate_prompt = (
                f"다음 {src} 텍스트를 {tgt}로 번역하세요:\n\n{q}"
            )
            if not voice_only:
                st.session_state["messages"].append({"role": "user", "content": f"[통역] {q}"})
                with st.chat_message("user"):
                    st.markdown(f"[통역 {src} → {tgt}] {q}")

            with st.spinner("통역 중..."):
                resp = bedrock.converse(
                    modelId=HAIKU_ID if st.session_state["model_key"] == "haiku" else SONNET_ID,
                    system=[{"text": TRANSLATE_SYSTEM}],
                    messages=[{"role": "user", "content": [{"text": translate_prompt}]}],
                    inferenceConfig={"maxTokens": 1024},
                )
                translated = resp["output"]["message"]["content"][0]["text"].strip()

            source_tag = f"{src} → {tgt} 통역"

            if not voice_only:
                with st.chat_message("assistant"):
                    st.markdown(translated)
                    st.caption(f"출처: {source_tag}")
            else:
                st.info(f"[{source_tag}] {translated}")

            st.session_state["messages"].append({
                "role": "assistant", "content": translated, "source": source_tag
            })

            if st.session_state["voice_on"]:
                audio = text_to_speech(translated, tgt, st.session_state["speed"])
                if audio:
                    autoplay_audio(audio, f"tr_{len(msgs)}")
            st.rerun()

        # 일반 대화 모드
        else:
            st.session_state["messages"].append({"role": "user", "content": q})
            if not voice_only:
                with st.chat_message("user"):
                    st.markdown(q)

            model_id = HAIKU_ID if st.session_state["model_key"] == "haiku" else SONNET_ID
            model    = get_model(model_id)

            # RAG 컨텍스트 구성
            rag_ctx = build_rag_context(q, st.session_state["doc_texts"])
            if rag_ctx:
                full_q = (
                    f"[업로드 문서 기반 컨텍스트]\n{rag_ctx}\n\n"
                    f"위 문서를 우선 참고하되, 문서에 없는 내용은 web_search 도구로 보완하여 답변하세요.\n\n"
                    f"질문: {q}"
                )
                source_hint = "문서+웹검색"
            else:
                full_q = q
                source_hint = "웹검색+도구"

            agent = Agent(
                model=model,
                tools=[weather_forecast, web_search, youtube_search, calculator, current_time],
                system_prompt=JARVIS_SYSTEM,
                callback_handler=None,
            )

            with st.spinner("JARVIS 처리 중..."):
                result   = agent(full_q)
                response = str(result).strip()

            # 출처 태그 결정
            if rag_ctx and ("web_search" not in response.lower()):
                source_tag = "📄 문서 기반"
            elif rag_ctx:
                source_tag = "📄 문서 + 🌐 웹검색"
            else:
                source_tag = "🌐 웹검색+도구"

            if not voice_only:
                with st.chat_message("assistant"):
                    st.markdown(response)
                    st.caption(f"출처: {source_tag}")
            else:
                st.success(response)

            st.session_state["messages"].append({
                "role": "assistant", "content": response, "source": source_tag
            })

            if st.session_state["voice_on"]:
                audio = text_to_speech(response, st.session_state["lang_key"], st.session_state["speed"])
                if audio:
                    autoplay_audio(audio, f"chat_{len(msgs)}")

            st.rerun()


# ════════════════════════════════════════════════════════════
# 탭 2: YouTube
# ════════════════════════════════════════════════════════════
with tab_youtube:
    st.subheader("▶ YouTube 영상 요약 & 검색")

    yt_col1, yt_col2 = st.columns([3, 1])
    with yt_col1:
        yt_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
    with yt_col2:
        yt_search_q = st.text_input("키워드 검색", placeholder="AWS Bedrock 튜토리얼")

    col_sum, col_search = st.columns(2)
    do_summarize = col_sum.button("📝 영상 요약 + 음성 안내", type="primary", use_container_width=True)
    do_search    = col_search.button("🔍 YouTube 검색", use_container_width=True)

    # ── 키워드 검색 ──
    if do_search and yt_search_q.strip():
        with st.spinner("YouTube 검색 중..."):
            try:
                from duckduckgo_search import DDGS
                results = DDGS().text(f"site:youtube.com {yt_search_q}", max_results=5)
                yt_results = [r for r in results
                              if "youtube.com/watch" in r.get("href", "") or
                                 "youtu.be" in r.get("href", "")]
            except Exception as e:
                yt_results = []
                st.error(f"검색 오류: {e}")

        if yt_results:
            st.markdown("**검색 결과**")
            for r in yt_results:
                vid = extract_video_id(r["href"])
                st.markdown(f"- [{r['title']}]({r['href']})")
                if vid:
                    with st.expander("미리 보기"):
                        st.components.v1.iframe(
                            f"https://www.youtube.com/embed/{vid}",
                            height=200,
                        )
        else:
            st.info("검색 결과가 없습니다.")

    # ── URL 요약 ──
    if do_summarize and yt_url.strip():
        vid_id = extract_video_id(yt_url.strip())
        if not vid_id:
            st.error("유효한 YouTube URL이 아닙니다.")
        else:
            # 영상 임베드
            st.markdown("**📺 영상**")
            st.components.v1.iframe(
                f"https://www.youtube.com/embed/{vid_id}",
                height=315,
            )

            with st.spinner("자막 추출 중..."):
                transcript, lang = get_transcript(vid_id)

            if not transcript:
                st.warning("자막을 찾을 수 없습니다. (자막 비활성화 영상이거나 지원하지 않는 언어)")
            else:
                st.caption(f"자막 언어: {lang} | 추출 길이: {len(transcript):,}자")

                with st.spinner("Claude가 요약 중..."):
                    model_id = HAIKU_ID if st.session_state["model_key"] == "haiku" else SONNET_ID
                    resp = bedrock.converse(
                        modelId=model_id,
                        system=[{"text": "당신은 YouTube 영상 요약 전문가입니다. 영상의 핵심 내용을 5문장 이내로 간결하게 한국어로 요약하세요."}],
                        messages=[{"role": "user", "content": [{"text": f"다음 자막을 요약하세요:\n\n{transcript}"}]}],
                        inferenceConfig={"maxTokens": 512},
                    )
                    summary = resp["output"]["message"]["content"][0]["text"].strip()

                st.markdown("**📝 요약**")
                st.info(summary)

                if st.session_state["voice_on"]:
                    with st.spinner("음성 생성 중..."):
                        audio = text_to_speech(
                            summary,
                            st.session_state["lang_key"],
                            st.session_state["speed"],
                        )
                    if audio:
                        st.markdown("**🔊 음성 안내**")
                        autoplay_audio(audio, f"yt_{vid_id}")
                else:
                    st.caption("음성 응답이 OFF 상태입니다. 사이드바에서 켤 수 있습니다.")
