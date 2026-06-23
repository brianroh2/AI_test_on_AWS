# Part 7 — JARVIS AI 콘솔 따라하기

AWS 브라우저(콘솔)에서 JARVIS AI에 필요한 서비스를 사전 확인하고 설정하는 단계별 가이드입니다.  
JARVIS AI는 Amazon Polly(TTS) + Amazon Transcribe(STT) + Strands Agent를 조합한 음성 비서입니다.

---

## JARVIS AI 구성 서비스

```
[사용자 음성]
    ↓ MP3 파일 업로드
[Amazon Transcribe] — 음성 → 텍스트 (STT)
    ↓ 텍스트
[Strands Agent + Claude] — 도구 포함 AI 응답 생성
    ↓ 응답 텍스트
[Amazon Polly] — 텍스트 → 음성 MP3 (TTS)
    ↓ MP3
[사용자 청취]
```

---

## 전체 흐름

```
1단계: Amazon Polly — 음성 합성 콘솔 체험
2단계: Amazon Transcribe — 음성 인식 콘솔 체험
3단계: IAM 권한 설정 (필수)
4단계: S3 버킷 사전 확인
5단계: Nova Sonic 지원 여부 확인
6단계: Python 코드 실행 순서
```

---

## 1단계. Amazon Polly — 텍스트 → 음성(TTS) 콘솔 체험

### 1-1. Polly 콘솔 접속

1. AWS 콘솔 상단 검색창에 `Polly` 입력 → **Amazon Polly** 클릭
2. 왼쪽 메뉴 → **Text-to-Speech** 클릭

---

### 1-2. 한국어 음성 (Seoyeon) 테스트

| 설정 항목 | 선택값 |
|-----------|--------|
| **Engine** | Neural |
| **Language** | Korean |
| **Voice** | Seoyeon |

**텍스트 입력창에 입력:**
```
안녕하세요. 저는 자비스입니다. 무엇을 도와드릴까요?
```

**Listen** 버튼 클릭 → 한국어 Neural TTS 음성 확인

---

### 1-3. 다국어 음성 테스트

아래 언어별로 설정을 바꿔가며 체험합니다:

| 언어 | Engine | Voice | 테스트 문장 |
|------|--------|-------|------------|
| 영어(미국) | Neural | Joanna | `Hello, I am JARVIS. How can I help you?` |
| 영어(영국) | Neural | Amy | `Hello, I am JARVIS. How can I assist you today?` |
| 일본어 | Neural | Kazuha | `こんにちは、ジャービスです。何かお手伝いできますか？` |
| 프랑스어 | Neural | Lea | `Bonjour, je suis JARVIS. Comment puis-je vous aider?` |
| 스페인어 | Neural | Lucia | `Hola, soy JARVIS. ¿En qué puedo ayudarte?` |
| 독일어 | Neural | Vicki | `Hallo, ich bin JARVIS. Wie kann ich Ihnen helfen?` |

> **Neural Engine이 Standard보다 훨씬 자연스럽습니다.**  
> JARVIS AI(P7_02, P7_04)는 모두 Neural Engine을 사용합니다.

---

### 1-4. SSML 속도 조절 체험

Polly는 SSML(Speech Synthesis Markup Language)로 말하기 속도를 조절할 수 있습니다.

**Input type** → **SSML** 선택 후 아래 입력:

**느린 속도:**
```xml
<speak>
  <prosody rate="slow">
    안녕하세요. 천천히 말씀드리겠습니다.
  </prosody>
</speak>
```

**빠른 속도:**
```xml
<speak>
  <prosody rate="fast">
    안녕하세요. 빠르게 말씀드리겠습니다.
  </prosody>
</speak>
```

> P7_04_jarvis_advanced_streamlit.py의 속도 선택(느림/보통/빠름)이 이 SSML을 사용합니다.

---

### 1-5. 음성 파일 다운로드

1. **Download** 버튼 클릭 → MP3 파일 저장
2. P7_01에서 생성되는 `/tmp/jarvis_test.mp3`와 동일한 방식입니다.

---

## 2단계. Amazon Transcribe — 음성 → 텍스트(STT) 콘솔 체험

### 2-1. Transcribe 콘솔 접속

1. AWS 콘솔 상단 검색창에 `Transcribe` 입력 → **Amazon Transcribe** 클릭
2. 왼쪽 메뉴 → **Real-time transcription** 클릭 (또는 **Transcription jobs**)

---

### 2-2. 실시간 전사 체험 (Real-time)

1. **Real-time transcription** 클릭
2. **Language** → `Korean, South Korea (ko-KR)` 선택
3. **Start streaming** 클릭
4. 마이크로 한국어로 말하기 → 실시간 텍스트 변환 확인

> **⚠️ SageMaker Code Editor 환경에서는 마이크 접근이 제한됩니다.**  
> 실시간 전사는 로컬 PC의 브라우저에서 체험하는 것을 권장합니다.

---

### 2-3. 파일 업로드 전사 Job (Transcription jobs)

P7_01에서 사용하는 방식입니다.

1. 왼쪽 메뉴 → **Transcription jobs** 클릭
2. **Create job** 클릭
3. 설정:

| 항목 | 입력값 |
|------|--------|
| **Job name** | `jarvis-test-job` |
| **Language** | Korean, South Korea (ko-KR) |
| **Input data** | S3 URI (이전에 업로드한 MP3 파일 경로) |
| **Output data** | S3 (자동 생성된 버킷 또는 지정 버킷) |

4. **Create** 클릭 → 상태: `In progress` → 완료: `Complete`
5. **View details** → **Transcription preview** 에서 변환된 텍스트 확인

> **소요 시간:** 보통 20~60초.  
> P7_01 코드가 자동으로 이 과정을 수행합니다.

---

### 2-4. 지원 언어 확인

1. **Create job** 화면의 **Language** 드롭다운 확인
2. 주요 지원 언어:

| 언어 | 코드 |
|------|------|
| 한국어 | `ko-KR` |
| 영어(미국) | `en-US` |
| 일본어 | `ja-JP` |
| 중국어(간체) | `zh-CN` |
| 프랑스어 | `fr-FR` |
| 스페인어 | `es-ES` |
| 독일어 | `de-DE` |

---

## 3단계. IAM 권한 설정 (필수)

JARVIS AI의 음성 기능은 SageMaker 기본 역할에 없는 권한이 필요합니다.

> **⚠️ 이 단계를 건너뛰면 P7_01 실행 시 AccessDeniedException 오류가 발생합니다.**  
> 자세한 따라하기는 `docs/SageMaker_IAM_권한설정.md` 를 참고하세요.

### 권한 확인 요약

| 서비스 | 필요 권한 | 없을 때 증상 |
|--------|----------|-------------|
| Amazon Polly | `polly:SynthesizeSpeech` | TTS 실패, 사이드바 오류 메시지 |
| Amazon Polly | `polly:DescribeVoices` | 음성 목록 조회 실패 |
| Amazon Transcribe | `transcribe:StartTranscriptionJob` 외 3개 | STT Job 생성 실패 |
| Amazon S3 | `s3:CreateBucket`, `s3:PutObject` 외 | 오디오 파일 업로드 실패 |

### 빠른 권한 확인 방법

터미널에서 실행:
```bash
aws sts get-caller-identity --query 'Arn' --output text
```

출력 예: `arn:aws:sts::560631060082:assumed-role/AmazonSageMaker-ExecutionRole-20260622T130537/SageMaker`

IAM 콘솔에서 역할명(`AmazonSageMaker-ExecutionRole-20260622T130537`) 검색 → 권한 확인.

---

## 4단계. S3 버킷 사전 확인

P7_01은 Transcribe Job용 오디오 파일을 S3에 업로드합니다.

### 4-1. S3 콘솔 접속

1. AWS 콘솔 → `S3` 검색 → **Amazon S3** 클릭
2. **Buckets** 목록 확인

### 4-2. P7_01 자동 생성 버킷 확인

P7_01을 실행하면 아래 이름의 버킷이 자동 생성됩니다:

```
jarvis-stt-tts-{AWS계정ID}
예: jarvis-stt-tts-560631060082
```

> 이미 실행한 경우 목록에 이 버킷이 보입니다.  
> 실습 완료 후 S3 비용 절감을 위해 버킷 내 파일을 삭제해도 됩니다.

### 4-3. 버킷 내 파일 구조

```
jarvis-stt-tts-{계정ID}/
  └── jarvis_test.mp3       ← Polly가 생성한 TTS 파일
  └── transcription-result/ ← Transcribe 결과 JSON
```

---

## 5단계. Nova Sonic 지원 여부 확인

### 5-1. Nova Sonic 모델 상태 확인

1. AWS 콘솔 → **Amazon Bedrock** 클릭
2. 왼쪽 메뉴 → **Model catalog** 클릭
3. 검색창에 `Nova Sonic` 입력

### 5-2. 현재 상태

| 모델 ID | 상태 | 비고 |
|---------|------|------|
| `amazon.nova-sonic-v1:0` | **LEGACY** | 교육 환경 실행 불가 |

> **P7_03_jarvis_nova_sonic.py** 는 Nova Sonic의 API 구조를 설명하는 참고용 파일입니다.  
> 실제 음성 스트리밍을 실행하려면 WebSocket 서버 및 마이크/스피커 연결이 필요합니다.  
> 교육 환경(SageMaker Code Editor)에서는 실행이 제한됩니다.

### 5-3. Nova Sonic vs 파이프라인 A 비교

| 항목 | 파이프라인 A (P7_02) | Nova Sonic |
|------|---------------------|------------|
| 구성 | Transcribe + LLM + Polly | 단일 통합 모델 |
| 응답 지연 | ~2~4초 | ~1초 미만 |
| API 방식 | REST (동기/비동기) | WebSocket 양방향 |
| Strands 도구 | 완전 지원 | 제한적 |
| 교육 환경 실행 | ✅ 가능 | ⚠️ 별도 인프라 필요 |
| 현재 상태 | **권장** | LEGACY (대기 중) |

---

## 6단계. P7 파일별 실행 방법

### P7_01 — STT/TTS 검증 (CLI)

```bash
# 권한 설정 후 실행
python3 P7_01_jarvis_stt_tts.py
```

**예상 출력:**
```
【STEP 1】 Amazon Polly TTS
  ✅ TTS 완료 — Seoyeon, ko-KR, Neural
  파일: /tmp/jarvis_test.mp3

【STEP 2】 Amazon Transcribe STT
  ✅ S3 업로드 완료
  Transcribe Job 시작 → 완료까지 최대 60초 대기
  ✅ 변환 결과: 안녕하세요 저는 자비스입니다...
```

---

### P7_02 — 기본 자비스 챗봇 (Streamlit, port 8512)

```bash
streamlit run P7_02_jarvis_streamlit.py \
  --server.port 8512 --server.headless true &
```

**주요 기능:**
- 텍스트 채팅 → Strands Agent 응답
- 음성 토글 ON → Polly Neural TTS 자동 재생
- 날씨/검색/계산 도구 자동 호출
- 모델 선택: Haiku(빠름) / Sonnet(고품질)

> **음성 토글 OFF 상태에서는 Polly 권한 없이도 텍스트 챗봇으로 완전 동작합니다.**

---

### P7_03 — Nova Sonic 안내 (CLI, 참고용)

```bash
python3 P7_03_jarvis_nova_sonic.py
```

Nova Sonic API 구조, WebSocket 이벤트 흐름을 출력합니다.  
실제 음성 실행은 하지 않습니다.

---

### P7_04 — 고급 자비스 (Streamlit, port 8514)

```bash
streamlit run P7_04_jarvis_advanced_streamlit.py \
  --server.port 8514 --server.headless true &
```

**주요 기능:**

| 탭 | 기능 |
|----|------|
| **자비스 대화** | 파일 업로드 RAG + 웹검색 자동 보완 |
| | 다국어 8개 음성 (한/영미영/일/중/프/스/독) |
| | 음성 속도 조절 (느림/보통/빠름) |
| | 음성+텍스트 / 음성전용 모드 전환 |
| | 통역 모드 (입력 언어 → 출력 언어) |
| **YouTube** | URL 입력 → 자막 추출 → Claude 요약 → Polly 음성 안내 |
| | 영상 임베드 재생 |
| | 키워드 검색 → YouTube 링크 |

---

## 콘솔 확인 체크리스트

```
□ Amazon Polly — Seoyeon Neural TTS 음성 확인
□ Amazon Polly — 다국어(최소 3개) 음성 체험
□ Amazon Polly — SSML 속도 조절 확인
□ Amazon Transcribe — 지원 언어 목록 확인
□ IAM — SageMaker 실행 역할에 Polly/Transcribe 권한 추가 완료
□ S3 — jarvis-stt-tts-{계정ID} 버킷 존재 여부 확인
□ Bedrock Model access — Claude Sonnet/Haiku Access granted 확인
□ Nova Sonic — LEGACY 상태 확인 (실행 불가)
□ P7_01 실행 → TTS/STT 왕복 검증 성공
□ P7_02 실행 → 텍스트+음성 챗봇 동작 확인
```

---

## 자주 발생하는 오류 및 해결

| 오류 메시지 | 원인 | 해결 방법 |
|-------------|------|-----------|
| `AccessDeniedException: polly:SynthesizeSpeech` | IAM 권한 없음 | `docs/SageMaker_IAM_권한설정.md` 따라하기 |
| `NoSuchBucket` | S3 버킷 미생성 | P7_01 실행 (자동 생성) 또는 수동 생성 |
| `InvalidParameterException: Engine Neural not supported` | 해당 언어에 Neural 엔진 미지원 | Standard로 변경 또는 다른 Voice 선택 |
| `TranscriptionJobNotFoundException` | Job 이름 오류 | P7_01 재실행 |
| Streamlit 음성 재생 안됨 | 브라우저 autoplay 차단 | 브라우저 주소창 옆 자물쇠 → 사운드 허용 |
