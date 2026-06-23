"""
P7_03_jarvis_nova_sonic.py
────────────────────────────────────────────────────────────────────
주제: Amazon Nova Sonic — 음성 통합 모델 구조 안내

Nova Sonic은 STT + LLM + TTS를 단일 API로 처리하는 통합 음성 모델입니다.
P7_02(파이프라인 A)와의 차이점 및 API 구조를 설명합니다.

이 파일에서는:
  03-1. Nova Sonic vs 파이프라인 A 비교
  03-2. Nova Sonic API 구조 및 호출 예시 코드 (텍스트 입출력 시뮬레이션)
  03-3. 언제 Nova Sonic이 유리한가

실행:
  python3 P7_03_jarvis_nova_sonic.py

※ 실제 Nova Sonic 음성 스트리밍 실행에는 WebSocket 서버 및
   마이크/스피커 연결이 필요합니다.
   SageMaker 교육 환경에서는 API 구조 안내로 대체합니다.
────────────────────────────────────────────────────────────────────
"""

import boto3
import json

REGION = "us-east-1"
SEP    = "─" * 60


# ═══════════════════════════════════════════════════════════════
# 03-1. Nova Sonic vs 파이프라인 A 비교
# ═══════════════════════════════════════════════════════════════
def step1_comparison():
    print(f"\n{SEP}")
    print("【STEP 1】 Nova Sonic vs 파이프라인 A 비교")
    print(SEP)

    print("""
  ┌─────────────────────┬──────────────────────┬──────────────────────┐
  │ 항목                │ 파이프라인 A (P7_02)  │ Nova Sonic            │
  ├─────────────────────┼──────────────────────┼──────────────────────┤
  │ 구성                │ Transcribe+LLM+Polly │ 단일 통합 모델        │
  │ 응답 지연           │ ~2~4초               │ ~1초 미만             │
  │ API 방식            │ REST (동기/비동기)   │ WebSocket 양방향      │
  │ 도구 사용           │ Strands 완전 지원    │ 제한적 (초기 단계)   │
  │ 음성 자연스러움     │ Neural TTS 수준      │ 더 자연스러움         │
  │ 비용                │ 서비스별 개별 청구   │ 통합 단일 요금        │
  │ 커스터마이징        │ 각 컴포넌트 독립 제어│ 제한적               │
  │ Streamlit 연동      │ 쉬움                 │ WebSocket 서버 필요   │
  │ 교육 환경 실행      │ ✅ 가능              │ ⚠️ 별도 인프라 필요  │
  └─────────────────────┴──────────────────────┴──────────────────────┘

  💡 결론:
     • 음성 응답 지연이 최우선이라면 → Nova Sonic
     • Strands 도구/메모리 통합이 중요하다면 → 파이프라인 A
     • 교육·프로토타입 환경 → 파이프라인 A가 현실적
    """)


# ═══════════════════════════════════════════════════════════════
# 03-2. Nova Sonic API 구조
# ═══════════════════════════════════════════════════════════════
def step2_api_structure():
    print(f"\n{SEP}")
    print("【STEP 2】 Nova Sonic API 구조")
    print(SEP)

    print("""
  Nova Sonic은 bedrock-runtime의 invoke_model_with_bidirectional_stream을
  사용하는 WebSocket 기반 양방향 스트리밍 API입니다.

  ── 연결 흐름 ───────────────────────────────────────────────

  클라이언트                          Nova Sonic (Bedrock)
      │                                        │
      │── sessionStart ──────────────────────→ │  (세션 초기화)
      │── promptStart ───────────────────────→ │  (대화 시작)
      │── systemPromptContent ───────────────→ │  (시스템 프롬프트)
      │── audioContent (PCM 16kHz) ──────────→ │  (음성 입력 스트림)
      │── contentBlockStop ──────────────────→ │  (입력 종료)
      │                                        │
      │ ←── textOutput ─────────────────────── │  (텍스트 중간 출력)
      │ ←── audioOutput (PCM) ──────────────── │  (음성 출력 스트림)
      │                                        │
      │── promptStop ───────────────────────→  │  (대화 종료)
      │── sessionStop ──────────────────────→  │  (세션 종료)

  ── 모델 ID ─────────────────────────────────────────────────

    amazon.nova-sonic-v1:0

  ── 주요 파라미터 ────────────────────────────────────────────

    inferenceConfig:
      maxTokens: 1024
      temperature: 0.7

    audioInputConfiguration:
      mediaType: "audio/lpcm"
      sampleRateHertz: 16000    ← 반드시 16kHz
      sampleSizeBits: 16
      channelCount: 1           ← 모노

    audioOutputConfiguration:
      mediaType: "audio/lpcm"
      sampleRateHertz: 24000    ← 출력은 24kHz
      sampleSizeBits: 16
      channelCount: 1
      voiceId: "tiffany"        ← 영어 기본 음성
    """)

    # 실제 boto3 코드 구조 예시 출력
    print("  ── Python 코드 구조 예시 ─────────────────────────────────")

    sample_code = '''
  import asyncio
  import boto3

  async def nova_sonic_session(system_prompt: str, audio_input: bytes):
      client = boto3.client("bedrock-runtime", region_name="us-east-1")

      # 이벤트 스트림 초기화
      async with client.invoke_model_with_bidirectional_stream(
          modelId="amazon.nova-sonic-v1:0",
      ) as stream:

          # 세션 시작
          await stream.input_stream.send({
              "event": {
                  "sessionStart": {
                      "inferenceConfiguration": {
                          "maxTokens": 1024,
                          "temperature": 0.7,
                      }
                  }
              }
          })

          # 시스템 프롬프트 전송
          await stream.input_stream.send({
              "event": {
                  "promptStart": {
                      "promptName": "jarvis-session",
                      "systemPrompt": system_prompt,
                  }
              }
          })

          # 음성 입력 스트리밍 (청크 단위)
          chunk_size = 1024
          for i in range(0, len(audio_input), chunk_size):
              chunk = audio_input[i:i+chunk_size]
              await stream.input_stream.send({
                  "event": {
                      "audioInput": {
                          "content": chunk,
                          "contentType": "audio/lpcm;rate=16000",
                      }
                  }
              })

          # 응답 수신
          async for response in stream.output_stream:
              if "audioOutput" in response.get("event", {}):
                  # 음성 출력 청크 처리
                  audio_chunk = response["event"]["audioOutput"]["content"]
                  yield audio_chunk  # 스피커로 즉시 재생
              elif "textOutput" in response.get("event", {}):
                  text = response["event"]["textOutput"]["content"]
                  print(f"텍스트: {text}")
    '''
    print(sample_code)


# ═══════════════════════════════════════════════════════════════
# 03-3. Nova Sonic 모델 접근 가능 여부 확인
# ═══════════════════════════════════════════════════════════════
def step3_availability_check():
    print(f"\n{SEP}")
    print("【STEP 3】 Nova Sonic 모델 접근 가능 여부 확인")
    print(SEP)

    client = boto3.client("bedrock", region_name=REGION)

    try:
        resp = client.get_foundation_model(
            modelIdentifier="amazon.nova-sonic-v1:0"
        )
        model_info = resp.get("modelDetails", {})
        print(f"\n  모델 ID:   {model_info.get('modelId', 'N/A')}")
        print(f"  모델명:    {model_info.get('modelName', 'N/A')}")
        print(f"  공급자:    {model_info.get('providerName', 'N/A')}")
        print(f"  입력 방식: {model_info.get('inputModalities', [])}")
        print(f"  출력 방식: {model_info.get('outputModalities', [])}")
        lifecycle = model_info.get("modelLifecycle", {})
        print(f"  상태:      {lifecycle.get('status', 'N/A')}")
        print(f"\n  ✅ Nova Sonic 모델 정보 조회 성공")
        print(f"     실제 음성 스트리밍 실행에는 별도 WebSocket 서버 구성 필요")
    except client.exceptions.ResourceNotFoundException:
        print(f"\n  ⚠️  nova-sonic-v1:0 — 이 계정/리전에서 아직 미지원")
        print(f"     us-east-1 리전 + 모델 접근 권한 요청 필요")
    except Exception as e:
        print(f"\n  ℹ️  조회 오류 ({type(e).__name__}): {e}")


# ═══════════════════════════════════════════════════════════════
# 03-4. 언제 Nova Sonic이 유리한가
# ═══════════════════════════════════════════════════════════════
def step4_when_to_use():
    print(f"\n{SEP}")
    print("【STEP 4】 언제 Nova Sonic을 선택할까?")
    print(SEP)

    print("""
  Nova Sonic이 유리한 경우:
  ────────────────────────────────────────────────────────
  ✅ 실시간 음성 대화가 핵심 (콜센터, 실시간 통역)
  ✅ 1초 미만의 응답 지연이 필요한 서비스
  ✅ STT/TTS 별도 서비스 비용을 줄이고 싶을 때
  ✅ 음성 감정·억양을 모델이 직접 제어해야 할 때

  파이프라인 A(Transcribe+LLM+Polly)가 유리한 경우:
  ────────────────────────────────────────────────────────
  ✅ Strands 도구/메모리/세션을 완전히 활용해야 할 때
  ✅ LLM을 Haiku/Sonnet/Opus 등 자유롭게 교체하고 싶을 때
  ✅ Streamlit 등 일반 웹 프레임워크에서 바로 실행할 때
  ✅ 교육·프로토타입 환경에서 빠르게 구축할 때
  ✅ 각 컴포넌트(STT/LLM/TTS)를 독립적으로 모니터링·최적화할 때

  현실적 추천:
  ────────────────────────────────────────────────────────
  • 프로토타입 / 교육  → 파이프라인 A (P7_02)
  • 프로덕션 음성 서비스 → Nova Sonic 검토
  • 도구+음성 모두 필요 → 파이프라인 A (Nova Sonic 도구 지원 성숙 후 전환)
    """)


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(" P7_03_jarvis_nova_sonic.py")
    print(" Amazon Nova Sonic 구조 안내 및 파이프라인 A 비교")
    print("=" * 60)

    step1_comparison()
    step2_api_structure()
    step3_availability_check()
    step4_when_to_use()

    print(f"\n{'=' * 60}")
    print(" 완료 — P7 시리즈 전체 완료!")
    print(f"{'=' * 60}")
    print("""
 실행 순서 요약:
   python3 P7_01_jarvis_stt_tts.py          # STT/TTS 단독 검증
   streamlit run P7_02_jarvis_streamlit.py \\
     --server.port 8512 --server.headless true  # 자비스 통합 UI
   python3 P7_03_jarvis_nova_sonic.py        # Nova Sonic 구조 안내
    """)
