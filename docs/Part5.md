# Part 5 — Amazon Bedrock Tool Use 학습 가이드

## 개요
Tool Use(Function Calling)는 LLM이 **외부 함수·API를 직접 호출**하게 하는 기능입니다.
모델이 "이 정보는 계산기/날씨API/DB에서 가져와야겠다"고 판단하면 스스로 도구를 호출합니다.

---

## AWS 브라우저(콘솔)에서 확인할 부분

| 확인 항목 | 경로 | 무엇을 보는가 |
|-----------|------|--------------|
| Playground | Bedrock → Playgrounds → Chat | 도구 JSON 직접 입력 후 동작 테스트 |
| 모델 도구 지원 여부 | Bedrock → Models → 모델 상세 | "Tool Use Supported" 항목 확인 |
| 호출 로그 | CloudWatch → Log Groups → `/aws/bedrock/` | 실제 tool_use 블록 JSON 확인 |

> **포인트**: Playground에서 tools JSON을 직접 작성하고 테스트하면 코드 작성 전에 스키마 설계를 검증할 수 있습니다.

---

## 파일별 핵심 내용 및 연관성

```
P5_01_tool_use_basic.py            ← 핵심 시작점
  └─ tool_use / tool_result 메시지 흐름 직접 구현
  └─ 이후 모든 P5 파일의 기본 패턴

P5_02_tool_use_schema.py
  └─ tools 파라미터 JSON Schema 설계 실습
  └─ required / enum / description 작성 방법

P5_03_tool_use_parallel.py
  └─ 여러 도구를 동시에 호출하는 패턴 (병렬 처리)
  └─ stopReason == "tool_use" 반복 루프

P5_04_tool_use_stream.py
  └─ 스트리밍 응답에서 tool_use 블록 조립 방법
  └─ inputJsonDelta 누적 → JSON 파싱

P5_05_tool_use_agent.py           ← 핵심
  └─ 자동 루프: 모델 응답 → 도구 실행 → 결과 전달 반복
  └─ P6 Strands Agent의 수동 구현 버전

P5_06_tool_use_chatbot.py
  └─ 멀티턴 대화 + Tool Use 통합 챗봇
```

---

## 코드에서 중요한 부분

### 1. Tool Use 메시지 흐름 — 핵심 사이클
```python
# 1단계: 모델에 도구 정의와 함께 질문
resp = bedrock.converse(
    modelId=MODEL_ID,
    messages=messages,
    tools=[{"toolSpec": {"name": "calculator", "inputSchema": {...}}}],
)

# 2단계: 모델이 도구 호출을 요청
if resp["stopReason"] == "tool_use":
    tool_block = resp["output"]["message"]["content"][0]
    tool_name  = tool_block["toolUse"]["name"]
    tool_input = tool_block["toolUse"]["input"]

    # 3단계: 실제 함수 실행
    result = my_calculator(**tool_input)

    # 4단계: 결과를 messages에 추가 후 재호출
    messages.append(resp["output"]["message"])
    messages.append({
        "role": "user",
        "content": [{"toolResult": {
            "toolUseId": tool_block["toolUse"]["toolUseId"],
            "content":   [{"text": str(result)}],
        }}],
    })
```

### 2. 도구 스키마 — description이 핵심
```python
# 모델이 도구를 언제 사용할지 판단하는 근거 = description
{
    "name": "get_weather",
    "description": "현재 날씨를 조회합니다. 날씨 관련 질문 시 반드시 이 도구를 사용하세요.",
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "도시 이름 (영문)"}
            },
            "required": ["city"]
        }
    }
}
```

### 3. 병렬 도구 호출 — content 배열에 여러 toolUse 블록
```python
# 모델이 한 번에 여러 도구를 요청하면 content 리스트에 여러 항목
for block in resp["output"]["message"]["content"]:
    if "toolUse" in block:
        # 각 도구 별도 실행
        results.append(execute_tool(block["toolUse"]))
```

### 4. 스트리밍 tool_use — inputJsonDelta 누적
```python
json_buffer = ""
for event in stream["stream"]:
    if "contentBlockDelta" in event:
        delta = event["contentBlockDelta"]["delta"]
        if "toolUse" in delta:
            json_buffer += delta["toolUse"].get("input", "")
# 스트림 끝에서 파싱
tool_input = json.loads(json_buffer)
```

---

## AWS만의 장점

| 장점 | 설명 |
|------|------|
| **Converse API 통합** | 모든 모델에 동일한 인터페이스 — 모델 교체 시 코드 변경 최소 |
| **병렬 도구 호출** | 모델이 독립적인 도구를 한 번의 응답에서 동시 요청 가능 |
| **`any` 강제 모드** | `toolChoice: {any: {}}` 로 모델이 반드시 도구를 사용하도록 강제 |
| **`auto` 자율 모드** | `toolChoice: {auto: {}}` 로 도구 사용 여부를 모델이 스스로 결정 |
| **Guardrails 연계** | Tool Use와 Guardrails 동시 적용 가능 — 도구 결과도 필터링 |
| **스트리밍 지원** | converse_stream으로 도구 응답을 실시간 스트리밍 가능 |

---

## P5 → P6 연관성

```
P5_05_tool_use_agent.py  (수동 구현)
         ↕ 동일 개념, 자동화
P6_02_strands_agent.py   (Strands가 루프 자동화)
P6_07_strands_tools.py   (strands_tools 내장 도구)
P6_08_strands_custom_tool.py  (@tool 데코레이터 커스텀 도구)
```

Strands는 P5에서 수동으로 구현한 "도구 응답 → messages 추가 → 재호출" 루프를 내부에서 자동으로 처리합니다.

---

## 실행 순서

```bash
python3 P5_01_tool_use_basic.py     # 기본 흐름 이해
python3 P5_02_tool_use_schema.py    # 스키마 설계 연습
python3 P5_03_tool_use_parallel.py  # 병렬 도구 호출
python3 P5_04_tool_use_stream.py    # 스트리밍 tool_use
python3 P5_05_tool_use_agent.py     # 자동 루프 에이전트
python3 P5_06_tool_use_chatbot.py   # 멀티턴 챗봇 통합
```
