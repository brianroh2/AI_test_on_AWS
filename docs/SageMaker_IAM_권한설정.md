# SageMaker Code Editor — P7 음성 기능 IAM 권한 설정 가이드

## 왜 권한이 필요한가?

SageMaker Code Editor는 **실행 역할(Execution Role)** 로 AWS 서비스를 호출합니다.
기본 역할(`AmazonSageMaker-ExecutionRole-*`)에는 Bedrock 권한은 포함되어 있지만,
P7 자비스 AI에서 사용하는 **Polly(TTS)**, **Transcribe(STT)**, **S3(오디오 임시 저장)** 권한은 포함되어 있지 않습니다.

| 서비스 | 용도 | 기본 권한 포함 여부 |
|--------|------|-------------------|
| Amazon Polly | 텍스트 → 음성(MP3) 변환 | ❌ 없음 |
| Amazon Transcribe | 음성(MP3) → 텍스트 변환 | ❌ 없음 |
| Amazon S3 | Transcribe 작업용 오디오 임시 저장 | ⚠️ 일부만 (신규 버킷 생성 권한 없을 수 있음) |

---

## 현재 실행 역할 확인 방법

터미널에서 아래 명령으로 현재 역할 이름을 확인합니다.

```bash
aws sts get-caller-identity --query 'Arn' --output text
```

출력 예시:
```
arn:aws:sts::560631060082:assumed-role/AmazonSageMaker-ExecutionRole-20260622T130537/SageMaker
```

역할 이름은 `assumed-role/` 뒤, `/SageMaker` 앞 부분입니다.
→ `AmazonSageMaker-ExecutionRole-20260622T130537`

---

## 권한 추가 방법 (따라하기)

### Step 1. AWS 콘솔 IAM 접속

1. 브라우저에서 [https://console.aws.amazon.com/iam](https://console.aws.amazon.com/iam) 접속
2. 왼쪽 메뉴 → **역할(Roles)** 클릭

---

### Step 2. SageMaker 실행 역할 검색

1. 검색창에 `AmazonSageMaker-ExecutionRole` 입력
2. 목록에서 본인 역할 클릭
   - 예: `AmazonSageMaker-ExecutionRole-20260622T130537`

> 역할이 여러 개라면 위에서 확인한 정확한 이름을 입력하세요.

---

### Step 3. 인라인 정책 추가

1. **권한(Permissions)** 탭 클릭
2. 오른쪽 위 **권한 추가(Add permissions)** 버튼 클릭
3. **인라인 정책 생성(Create inline policy)** 선택

---

### Step 4. JSON 정책 입력

1. 편집기 상단 탭에서 **JSON** 클릭
2. 기존 내용을 모두 지우고 아래 JSON을 붙여넣기

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "JarvisPollyAccess",
      "Effect": "Allow",
      "Action": [
        "polly:SynthesizeSpeech",
        "polly:DescribeVoices"
      ],
      "Resource": "*"
    },
    {
      "Sid": "JarvisTranscribeAccess",
      "Effect": "Allow",
      "Action": [
        "transcribe:StartTranscriptionJob",
        "transcribe:GetTranscriptionJob",
        "transcribe:ListTranscriptionJobs",
        "transcribe:DeleteTranscriptionJob"
      ],
      "Resource": "*"
    },
    {
      "Sid": "JarvisS3Access",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:HeadBucket"
      ],
      "Resource": [
        "arn:aws:s3:::jarvis-stt-tts-*",
        "arn:aws:s3:::jarvis-stt-tts-*/*"
      ]
    }
  ]
}
```

3. **다음(Next)** 클릭

---

### Step 5. 정책 이름 입력 후 저장

1. **정책 이름(Policy name)** 란에 입력:
   ```
   JarvisSTTTTSPolicy
   ```
2. **정책 생성(Create policy)** 클릭

---

### Step 6. 적용 확인

1. 역할 페이지로 돌아와 **권한 정책** 목록에 `JarvisSTTTTSPolicy` 가 보이면 완료
2. 터미널에서 아래 명령으로 즉시 검증:

```bash
python3 P7_01_jarvis_stt_tts.py
```

권한이 정상 적용됐다면 STT/TTS 검증이 시작됩니다.

---

## 권한 적용 후 예상 출력

```
============================================================
 P7_01_jarvis_stt_tts.py
 Amazon Transcribe (STT) + Amazon Polly (TTS) 검증
============================================================
  S3 버킷 생성: jarvis-stt-tts-560631060082

────────────────────────────────────────────────────────────
【STEP 1】 Amazon Polly TTS — 텍스트 → 음성
────────────────────────────────────────────────────────────
  입력 텍스트: 안녕하세요. 저는 자비스입니다...
  ✅ TTS 완료
     음성 엔진: Neural (Seoyeon, ko-KR)
     파일 크기: 12,345 bytes
     저장 경로: /tmp/jarvis_test.mp3
...
```

---

## 파일별 권한 사용 현황

| 파일 | 필요 권한 | 권한 없을 때 동작 |
|------|----------|------------------|
| `P7_01_jarvis_stt_tts.py` | Polly + Transcribe + S3 | 권한 부족 안내 + IAM 정책 JSON 출력 후 종료 |
| `P7_02_jarvis_streamlit.py` | Polly (TTS 토글 ON 시) | 사이드바 오류 메시지, 텍스트 응답은 정상 동작 |
| `P7_03_jarvis_nova_sonic.py` | 없음 (정보 조회만) | 정상 실행 |

---

## 정책 삭제 방법 (실습 완료 후)

실습 완료 후 불필요한 권한을 제거하려면:

1. IAM → 역할 → `AmazonSageMaker-ExecutionRole-*` 클릭
2. **권한(Permissions)** 탭 → `JarvisSTTTTSPolicy` 옆 **삭제(X)** 클릭
3. 확인 창에서 **삭제** 클릭

---

## 자주 묻는 질문

**Q. 권한 추가 후 바로 적용되나요?**
A. 네, IAM 정책은 즉시 적용됩니다. 재시작 불필요.

**Q. S3 버킷이 이미 있으면 CreateBucket 권한 없어도 되나요?**
A. P7_01이 처음 실행 시 버킷을 자동 생성합니다. 이미 존재하면 HeadBucket으로 확인만 하므로 CreateBucket은 최초 1회만 필요합니다.

**Q. 다른 파트(P2~P6) 실행에도 이 권한이 필요한가요?**
A. 아니요. P2~P6는 Bedrock API만 사용하며 기본 역할 권한으로 충분합니다.

**Q. P7_02 Streamlit에서 음성 OFF로 쓰면 권한 없어도 되나요?**
A. 네. TTS 토글을 끄면 Polly를 호출하지 않아 권한 없이도 텍스트 챗봇으로 완전히 동작합니다.
