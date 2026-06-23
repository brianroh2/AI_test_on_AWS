# Part 5 — Tool Use 콘솔 따라하기

AWS 브라우저(콘솔)에서 Tool Use(도구 사용) 동작을 직접 확인하는 단계별 가이드입니다.  
Tool Use는 코드 실습이 핵심이지만, 콘솔에서도 모델 호출 로그와 동작을 확인할 수 있습니다.

---

## Tool Use 란?

모델이 스스로 "이 질문에는 날씨 정보가 필요하다"고 판단하면 도구 호출을 요청하고,  
우리 코드가 실제 날씨 API를 호출한 뒤 결과를 돌려주면 모델이 최종 답변을 만드는 방식입니다.

```
[사용자 질문]
  → 모델: "get_weather 도구 필요" (stopReason: tool_use)
  → 우리 코드: wttr.in API 호출 → 결과 반환
  → 모델: 결과 바탕으로 최종 답변 생성
```

---

## 전체 흐름

```
1단계: 콘솔 Playgrounds에서 Tool Use 직접 체험
2단계: 모델 지원 여부 확인
3단계: CloudWatch에서 API 호출 로그 확인 (선택)
4단계: Python 코드 실습으로 연계
```

---

## 1단계. 콘솔 Playgrounds에서 Tool Use 체험

### 1-1. Chat Playground 접속

1. AWS 콘솔 → 상단 검색창에 `Bedrock` 입력 → **Amazon Bedrock** 클릭
2. 왼쪽 메뉴 → **Playgrounds** → **Chat** 클릭
3. 오른쪽 위 **Select model** 클릭
4. 모델 선택:
   - **Anthropic** → **Claude Sonnet 4** 선택 (Tool Use 지원 모델)
   - **Apply** 클릭

---

### 1-2. Tool 정의 추가

1. Chat Playground 화면 오른쪽 설정 패널에서 **Tool use** 섹션 찾기
2. **Add tool** 클릭
3. 아래 내용 입력:

**Tool 이름 및 설명:**

| 항목 | 입력값 |
|------|--------|
| **Tool name** | `get_weather` |
| **Description** | `도시의 현재 날씨를 조회합니다. 도시명은 영문으로 입력합니다.` |

**Input schema (JSON):**

```json
{
  "type": "object",
  "properties": {
    "city": {
      "type": "string",
      "description": "날씨를 조회할 도시명 (영문). 예: Seoul, Tokyo, New York"
    }
  },
  "required": ["city"]
}
```

4. **Save** 클릭

---

### 1-3. Tool Use 동작 확인

채팅창에 아래 질문을 입력합니다:

```
서울 지금 날씨 어때?
```

**예상 동작:**
- 모델이 `get_weather` 도구를 호출하려고 시도합니다.
- 콘솔에서는 실제 날씨 API가 연결되어 있지 않으므로, 모델이 도구 호출 요청(`tool_use`)을 반환합니다.
- 화면에 **Tool use** 블록이 표시되며 `{"city": "Seoul"}` 형태의 인자가 보입니다.

> **이것이 핵심입니다:**  
> 콘솔에서 모델이 스스로 "도구 호출이 필요하다"고 판단하는 것을 눈으로 확인할 수 있습니다.  
> 실제 날씨 데이터는 Python 코드(P5_02~P5_04)에서 wttr.in API를 연결해야 받을 수 있습니다.

---

### 1-4. 다중 도구 추가 체험

**Add tool**을 한 번 더 클릭하여 시간 도구도 추가합니다:

| 항목 | 입력값 |
|------|--------|
| **Tool name** | `get_time` |
| **Description** | `도시의 현재 시간을 반환합니다.` |

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "city": {
      "type": "string",
      "description": "시간을 조회할 도시명. 예: 서울, Tokyo, London"
    }
  },
  "required": ["city"]
}
```

채팅창에 복합 질문 입력:
```
도쿄 날씨와 현재 시간을 알려줘
```

> 모델이 `get_weather`와 `get_time` 두 도구를 차례로 또는 동시에 호출하는 것을 확인할 수 있습니다.

---

## 2단계. Tool Use 지원 모델 확인

### 콘솔에서 지원 모델 확인

1. 왼쪽 메뉴 → **Model catalog** 클릭
2. 검색창에 모델명 입력 후 클릭
3. 상세 페이지에서 **Supported use cases** 항목 확인

| 모델 | Tool Use 지원 |
|------|--------------|
| Claude Sonnet 4.6 | ✅ |
| Claude Haiku 4.5 | ✅ |
| Amazon Nova Pro | ✅ |
| Amazon Nova Lite | ✅ |
| Amazon Titan Text | ❌ |
| Stable Diffusion | ❌ |

> **⚠️ 주의:** Tool Use 미지원 모델에 `toolConfig`를 전달하면  
> `ValidationException` 오류가 발생합니다.

---

## 3단계. API 호출 로그 확인 (선택)

Python 코드를 실행한 후 CloudWatch에서 실제 호출 기록을 확인할 수 있습니다.

1. AWS 콘솔 → **CloudWatch** 검색 → 클릭
2. 왼쪽 메뉴 → **Log groups** 클릭
3. `/aws/bedrock/modelinvocations` 검색

> **⚠️ 로그 그룹이 없을 수 있습니다.**  
> Bedrock 모델 호출 로깅은 별도 활성화가 필요합니다.  
> Bedrock → **Settings** → **Model invocation logging** → Enable

---

## 4단계. Tool Use 4단계 흐름 정리

콘솔에서 확인한 동작이 코드에서 어떻게 구현되는지 비교합니다.

| 단계 | 콘솔에서 보이는 것 | Python 코드에서 하는 것 |
|------|-------------------|------------------------|
| **1** | 질문 입력 | `converse(messages, toolConfig)` 호출 |
| **2** | Tool use 블록 표시 | `stopReason == "tool_use"` 확인 |
| **3** | (콘솔은 여기서 멈춤) | 실제 API 호출 → `toolResult` 반환 |
| **4** | - | `toolResult` 담아 `converse` 재호출 → 최종 답변 |

---

## 콘솔 체험 후 Python 코드 실행 순서

```bash
python3 P5_01_tooluse_setup.py      # 환경 및 wttr.in 접근 확인
python3 P5_02_tooluse_4step.py      # 4단계 흐름 전체 실행
python3 P5_03_tooluse_tooluse.py    # toolUse 블록 파싱
python3 P5_04_tooluse_toolresult.py # toolResult 반환 완전 구현
python3 P5_05_tooluse_multi.py      # 날씨 + 시간 다중 도구
python3 P5_06_tooluse_chatbot.py    # 대화 히스토리 + Tool Use 챗봇
```

---

## 핵심 주의사항 요약

```
□ Tool Use는 Claude / Nova 계열만 지원 (Titan 등 미지원)
□ toolConfig 전달 시 미지원 모델 → ValidationException
□ 콘솔 Playground는 도구 호출 요청까지만 확인 가능
□ 실제 외부 API 연결(wttr.in 등)은 Python 코드에서 처리
□ 다중 도구: 모델이 필요에 따라 여러 도구를 선택적으로 호출
```
