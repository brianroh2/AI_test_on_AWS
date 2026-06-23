# AI_test_on_AWS

Amazon Bedrock 기반 AI 개발 실습 코드 모음입니다.

## 구성

| 파트 | 주제 | 주요 파일 |
|------|------|-----------|
| P1 | Bedrock API 기초 | `P1_test_01~04_*.py` |
| P2 | 프롬프트 엔지니어링 | `P2_01~06_*.py` |
| P3 | RAG (Knowledge Base) | `P3_01~08_*.py` |
| P4 | Guardrails (안전 필터) | `P4_01~07_*.py` |
| P5 | Tool Use (도구 사용) | `P5_01~06_*.py` |
| P6 | Strands Agentic AI | `P6_01~11_*.py` |
| P7 | JARVIS 음성 AI | `P7_01~04_*.py` |

## 환경

- Python 3.12 (conda base)
- Amazon SageMaker Studio Code Editor
- Region: us-east-1

## 주요 의존성

```bash
pip install boto3 streamlit strands-agents strands-agents-tools \
            pdfplumber youtube-transcript-api duckduckgo-search
```

## 실행 예시

```bash
# P4 Guardrails
python3 P4_04_guardrails_create.py
python3 P4_05_guardrails_converse.py

# P6 Strands Agent
python3 P6_01_strands_setup.py
python3 P6_10_strands_react.py

# P7 JARVIS
streamlit run P7_02_jarvis_streamlit.py --server.port 8512 --server.headless true
streamlit run P7_04_jarvis_advanced_streamlit.py --server.port 8514 --server.headless true
```

## 콘솔 따라하기 문서

`docs/` 폴더에 AWS 콘솔 UI 기반 단계별 가이드가 있습니다.

| 문서 | 내용 |
|------|------|
| `Part4_콘솔_따라하기.md` | Guardrail 생성 및 테스트 |
| `Part5_콘솔_따라하기.md` | Tool Use Playground 체험 |
| `Part6_콘솔_따라하기.md` | Strands / ReAct / ReWOO |
| `Part7_콘솔_따라하기.md` | Polly TTS / Transcribe / Nova Sonic |

## 주의사항

- `guardrail_config.json` / `rag_config.json` — AWS 리소스 ID 포함, `.gitignore` 처리됨
- Polly TTS 사용 시 SageMaker 실행 역할에 `polly:SynthesizeSpeech` 권한 필요
- `docs/SageMaker_IAM_권한설정.md` 참고
