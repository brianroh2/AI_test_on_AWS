"""
P7_01_jarvis_stt_tts.py
────────────────────────────────────────────────────────────────────
주제: 자비스 AI 음성 레이어 — Amazon Transcribe (STT) + Amazon Polly (TTS)

자비스 음성 비서의 귀(STT)와 입(TTS)을 독립적으로 검증합니다.

01-1. Polly TTS — 텍스트 → 음성 MP3 생성 (Neural 엔진)
01-2. Transcribe STT — 오디오 파일 → 텍스트 (비동기 Job)
01-3. 왕복 검증 — TTS 생성 MP3 → STT → 원문 비교

실행:
  python3 P7_01_jarvis_stt_tts.py

※ Transcribe Job은 완료까지 20~40초 소요됩니다.
   오디오 파일 → S3 업로드 → Transcribe → 결과 다운로드 순서로 진행.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  SageMaker 실행 역할 추가 권한 필요
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SageMaker Code Editor의 기본 실행 역할에는
Polly / Transcribe / S3 권한이 포함되어 있지 않습니다.

처음 실행 시 권한 부족 안내와 IAM 정책 JSON이 자동 출력됩니다.
자세한 권한 추가 방법은 아래 파일을 참고하세요:

  docs/SageMaker_IAM_권한설정.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
────────────────────────────────────────────────────────────────────
"""

import boto3
import time
import json
import os
from pathlib import Path

REGION      = "us-east-1"
BUCKET_NAME = f"jarvis-stt-tts-{boto3.client('sts').get_caller_identity()['Account']}"
TTS_FILE    = Path("/tmp/jarvis_test.mp3")
SEP         = "─" * 60

polly       = boto3.client("polly",        region_name=REGION)
transcribe  = boto3.client("transcribe",   region_name=REGION)
s3          = boto3.client("s3",           region_name=REGION)

# ── IAM 권한 사전 확인 ────────────────────────────────────────
def check_permissions():
    """필요한 IAM 권한을 사전 점검하고 없으면 안내 출력."""
    missing = []
    try:
        polly.describe_voices(LanguageCode="ko-KR")
    except Exception as e:
        if "AccessDenied" in str(e) or "not authorized" in str(e):
            missing.append("polly:SynthesizeSpeech / polly:DescribeVoices")

    try:
        transcribe.list_transcription_jobs(MaxResults=1)
    except Exception as e:
        if "AccessDenied" in str(e) or "not authorized" in str(e):
            missing.append("transcribe:StartTranscriptionJob / transcribe:GetTranscriptionJob")

    if missing:
        print("\n  ⚠️  IAM 권한 부족 — 아래 권한을 SageMaker 실행 역할에 추가하세요.")
        print(f"  역할: AmazonSageMaker-ExecutionRole-*")
        print(f"\n  필요한 서비스 권한:")
        for m in missing:
            print(f"    • {m}")
        print(f"""
  AWS 콘솔 추가 방법:
    1. IAM → 역할 → AmazonSageMaker-ExecutionRole-* 검색
    2. 권한 추가 → 인라인 정책 생성
    3. 아래 JSON 정책 붙여넣기:

  {{
    "Version": "2012-10-17",
    "Statement": [
      {{
        "Effect": "Allow",
        "Action": [
          "polly:SynthesizeSpeech",
          "polly:DescribeVoices",
          "transcribe:StartTranscriptionJob",
          "transcribe:GetTranscriptionJob",
          "transcribe:ListTranscriptionJobs"
        ],
        "Resource": "*"
      }}
    ]
  }}

    4. 정책 이름: JarvisSTTTTSPolicy → 저장
  """)
        return False
    return True


# ── S3 버킷 확인/생성 ─────────────────────────────────────────
def ensure_bucket():
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print(f"  S3 버킷 존재: {BUCKET_NAME}")
    except Exception:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        print(f"  S3 버킷 생성: {BUCKET_NAME}")


# ═══════════════════════════════════════════════════════════════
# 01-1. Polly TTS — 텍스트 → MP3
# ═══════════════════════════════════════════════════════════════
def step1_polly_tts(text: str) -> Path:
    print(f"\n{SEP}")
    print("【STEP 1】 Amazon Polly TTS — 텍스트 → 음성")
    print(SEP)
    print(f"\n  입력 텍스트: {text}")

    resp = polly.synthesize_speech(
        Text=text,
        OutputFormat="mp3",
        VoiceId="Seoyeon",          # 한국어 Neural 음성
        Engine="neural",            # Neural TTS (더 자연스러운 음성)
        LanguageCode="ko-KR",
    )

    audio_bytes = resp["AudioStream"].read()
    TTS_FILE.write_bytes(audio_bytes)

    print(f"\n  ✅ TTS 완료")
    print(f"     음성 엔진: Neural (Seoyeon, ko-KR)")
    print(f"     파일 크기: {len(audio_bytes):,} bytes")
    print(f"     저장 경로: {TTS_FILE}")
    print(f"\n  💡 Polly 음성 종류:")
    print(f"     standard — 기존 TTS (빠름, 저렴)")
    print(f"     neural   — 딥러닝 기반 (자연스럽지만 약간 느림)")
    print(f"     long-form — 장문 낭독 최적화 (영어 전용)")
    print(f"     generative — 가장 자연스러움 (영어 전용, 비쌈)")

    return TTS_FILE


# ═══════════════════════════════════════════════════════════════
# 01-2. Transcribe STT — MP3 → 텍스트
# ═══════════════════════════════════════════════════════════════
def step2_transcribe_stt(audio_path: Path) -> str:
    print(f"\n{SEP}")
    print("【STEP 2】 Amazon Transcribe STT — 음성 → 텍스트")
    print(SEP)

    # S3 업로드
    s3_key = f"jarvis-test/{audio_path.name}"
    s3.upload_file(str(audio_path), BUCKET_NAME, s3_key)
    s3_uri = f"s3://{BUCKET_NAME}/{s3_key}"
    print(f"\n  S3 업로드: {s3_uri}")

    # Transcribe 비동기 Job 시작
    job_name = f"jarvis-test-{int(time.time())}"
    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": s3_uri},
        MediaFormat="mp3",
        LanguageCode="ko-KR",
        Settings={
            "ShowSpeakerLabels": False,
            "ChannelIdentification": False,
        },
    )
    print(f"  Job 시작: {job_name}")
    print(f"  완료까지 20~40초 대기 중...")

    # 완료 대기
    for i in range(60):
        time.sleep(3)
        status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        state  = status["TranscriptionJob"]["TranscriptionJobStatus"]
        print(f"  [{i*3:3d}초] 상태: {state}", end="\r")
        if state == "COMPLETED":
            break
        if state == "FAILED":
            reason = status["TranscriptionJob"].get("FailureReason", "알 수 없음")
            print(f"\n  ❌ Transcribe 실패: {reason}")
            return ""

    print()
    transcript_uri = (
        status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
    )

    # 결과 다운로드
    import urllib.request
    with urllib.request.urlopen(transcript_uri) as f:
        result = json.loads(f.read())

    transcript = result["results"]["transcripts"][0]["transcript"]
    confidence_list = [
        float(item["alternatives"][0]["confidence"])
        for item in result["results"]["items"]
        if item["type"] == "pronunciation" and item["alternatives"]
    ]
    avg_conf = sum(confidence_list) / len(confidence_list) if confidence_list else 0

    print(f"\n  ✅ STT 완료")
    print(f"     인식 텍스트: {transcript}")
    print(f"     평균 신뢰도: {avg_conf:.2%}")
    print(f"\n  💡 Transcribe 주요 기능:")
    print(f"     • 실시간 스트리밍: start_stream_transcription (WebSocket)")
    print(f"     • 배치 처리: start_transcription_job (이 예제)")
    print(f"     • 화자 분리: ShowSpeakerLabels=True")
    print(f"     • 커스텀 단어: VocabularyName 지정")

    return transcript


# ═══════════════════════════════════════════════════════════════
# 01-3. 왕복 검증 — TTS → STT → 원문 비교
# ═══════════════════════════════════════════════════════════════
def step3_roundtrip(original: str, transcribed: str):
    print(f"\n{SEP}")
    print("【STEP 3】 왕복 검증 — 원문 vs 인식 결과")
    print(SEP)

    print(f"\n  원문:   {original}")
    print(f"  인식:   {transcribed}")

    # 간단한 유사도 (공통 단어 비율)
    orig_words  = set(original.replace(" ", ""))
    trans_words = set(transcribed.replace(" ", ""))
    if orig_words:
        sim = len(orig_words & trans_words) / len(orig_words)
        print(f"\n  문자 유사도: {sim:.0%}")
        if sim >= 0.8:
            print(f"  ✅ 인식 품질 양호")
        else:
            print(f"  ⚠️ 인식 차이 존재 (짧은 문장이거나 발음 특성)")

    print(f"""
  ─ 자비스 AI 음성 파이프라인 ────────────────────────────
  방법 A (파이프라인) — 현재 구조:

    [마이크/오디오]
         ↓
    Amazon Transcribe (STT)   ← 귀
         ↓ 텍스트
    Strands Agent + Haiku     ← 두뇌
         ↓ 텍스트
    Amazon Polly (TTS)        ← 입
         ↓
    [스피커/오디오]

  특징:
    • 각 컴포넌트 독립 교체 가능
    • Strands 도구/메모리 그대로 활용
    • Haiku 사용 시 비용 최소화
    • 문장 단위 스트리밍으로 응답속도 개선 가능
  ─────────────────────────────────────────────────────────
    """)


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(" P7_01_jarvis_stt_tts.py")
    print(" Amazon Transcribe (STT) + Amazon Polly (TTS) 검증")
    print("=" * 60)

    # IAM 권한 사전 점검
    if not check_permissions():
        print("\n권한 추가 후 다시 실행하세요.")
        exit(0)

    TEST_TEXT = "안녕하세요. 저는 자비스입니다. 오늘 서울 날씨를 알려드리겠습니다."

    # STEP 1: TTS
    ensure_bucket()
    audio_file = step1_polly_tts(TEST_TEXT)

    # STEP 2: STT
    transcribed = step2_transcribe_stt(audio_file)

    # STEP 3: 왕복 검증
    if transcribed:
        step3_roundtrip(TEST_TEXT, transcribed)

    print(f"\n{'=' * 60}")
    print("완료 — 다음: P7_02_jarvis_streamlit.py")
    print("=" * 60)
