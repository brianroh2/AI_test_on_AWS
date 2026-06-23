# ============================================================
# 파일명: P1_test_02_streaming.py
# 주제: Amazon Bedrock 스트리밍 응답 (converse_stream)
#
# 【이 코드가 하는 일】
#   일반 converse()는 모델이 답변을 완성한 뒤 한꺼번에 반환합니다.
#   스트리밍(converse_stream)은 모델이 단어를 생성하는 즉시
#   조각(chunk)으로 실시간 전달합니다.
#   → 사용자가 긴 답변을 기다리지 않고 바로 읽기 시작할 수 있습니다.
#   → 실제 ChatGPT, Claude.ai 처럼 글자가 흘러나오는 효과입니다.
#
# 【실습 구성】
#   샘플 1: 기본 스트리밍 — 실시간 출력
#   샘플 2: 스트림 이벤트 구조 확인 — 어떤 데이터가 오는지 보기
#   샘플 3: 스트리밍 + 대화 기록 누적 (멀티턴 연동)
#   샘플 4: 토큰 사용량 확인 (비용 파악)
# ============================================================

import boto3
import time

# ── 공통 설정 ────────────────────────────────────────────────
REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

# bedrock-runtime 클라이언트 생성
# SageMaker IAM Role이 자동으로 인증을 처리하므로 키 설정 불필요
bedrock = boto3.client("bedrock-runtime", region_name=REGION)


# ============================================================
# 샘플 1: 기본 스트리밍
# converse_stream()은 응답을 EventStream으로 반환합니다.
# stream["stream"]을 순회하며 chunk가 올 때마다 즉시 출력합니다.
# ============================================================
print("=" * 55)
print("샘플 1: 기본 스트리밍 — 실시간 출력")
print("=" * 55)

# converse_stream 호출 (converse와 파라미터 구조 동일)
stream = bedrock.converse_stream(
    modelId=MODEL_ID,
    messages=[
        {"role": "user", "content": [{"text": "파이썬의 장점을 5가지 설명해줘."}]}
    ],
    inferenceConfig={"maxTokens": 500, "temperature": 0.7}
)

full_text = ""  # 전체 응답을 모으는 변수

# EventStream 순회: 이벤트 타입에 따라 분기 처리
for event in stream["stream"]:

    # contentBlockDelta: 실제 텍스트 조각이 담긴 이벤트
    if "contentBlockDelta" in event:
        chunk = event["contentBlockDelta"]["delta"]["text"]
        print(chunk, end="", flush=True)  # flush=True: 버퍼 없이 즉시 출력
        full_text += chunk

    # messageStop: 모델이 생성을 완료했다는 신호
    elif "messageStop" in event:
        print()  # 줄바꿈
        print(f"\n[생성 완료] 종료 이유: {event['messageStop']['stopReason']}")

print()


# ============================================================
# 샘플 2: 스트림 이벤트 구조 확인
# 실제로 어떤 이벤트들이 순서대로 오는지 타입만 출력해봅니다.
# 디버깅이나 이벤트 처리 로직 설계 시 유용합니다.
# ============================================================
print("=" * 55)
print("샘플 2: 스트림 이벤트 구조 확인")
print("=" * 55)

stream2 = bedrock.converse_stream(
    modelId=MODEL_ID,
    messages=[
        {"role": "user", "content": [{"text": "안녕이라고만 해줘."}]}
    ],
    inferenceConfig={"maxTokens": 50}
)

event_count = 0
for event in stream2["stream"]:
    event_type = list(event.keys())[0]  # 이벤트 타입 추출
    event_count += 1

    if event_type == "contentBlockDelta":
        # 텍스트 조각의 길이만 표시
        text_chunk = event["contentBlockDelta"]["delta"]["text"]
        print(f"  [{event_count}] {event_type}: '{text_chunk}'")
    elif event_type == "metadata":
        # 토큰 사용량 정보
        usage = event["metadata"].get("usage", {})
        print(f"  [{event_count}] {event_type}: 입력토큰={usage.get('inputTokens')}, "
              f"출력토큰={usage.get('outputTokens')}")
    else:
        print(f"  [{event_count}] {event_type}")

print()


# ============================================================
# 샘플 3: 스트리밍 + 멀티턴 대화 기록 누적
# 스트리밍으로 받은 응답도 history에 쌓아서 대화 흐름을 유지합니다.
# 실제 챗봇 구현 시 핵심 패턴입니다.
# ============================================================
print("=" * 55)
print("샘플 3: 스트리밍 + 멀티턴 대화 기록 누적")
print("=" * 55)

history = []  # 대화 기록 저장 리스트

def stream_chat(user_input):
    """스트리밍으로 응답받고, 완성된 텍스트를 history에 누적하는 함수"""

    # 사용자 메시지를 history에 추가
    history.append({
        "role": "user",
        "content": [{"text": user_input}]
    })

    # 스트리밍 호출 (history 전체를 messages로 전달 → 문맥 유지)
    stream = bedrock.converse_stream(
        modelId=MODEL_ID,
        messages=history,
        inferenceConfig={"maxTokens": 300}
    )

    print(f"Claude: ", end="", flush=True)

    reply = ""
    for event in stream["stream"]:
        if "contentBlockDelta" in event:
            chunk = event["contentBlockDelta"]["delta"]["text"]
            print(chunk, end="", flush=True)  # 실시간 출력
            reply += chunk

    print()  # 줄바꿈

    # 완성된 응답을 assistant 역할로 history에 추가
    history.append({
        "role": "assistant",
        "content": [{"text": reply}]
    })

    return reply

# 멀티턴 대화 테스트
print(f"사용자: 나는 SKT에서 일하고 있어.")
stream_chat("나는 SKT에서 일하고 있어.")

print(f"\n사용자: 내가 어디서 일한다고 했지?")
stream_chat("내가 어디서 일한다고 했지?")

print()


# ============================================================
# 샘플 4: 토큰 사용량 확인
# 토큰 = 비용의 기준. 입력/출력 토큰 수를 파악해두면
# 실제 서비스에서 비용을 예측하고 최적화할 수 있습니다.
# ============================================================
print("=" * 55)
print("샘플 4: 토큰 사용량 확인 (비용 파악)")
print("=" * 55)

stream3 = bedrock.converse_stream(
    modelId=MODEL_ID,
    messages=[
        {"role": "user", "content": [{"text": "AWS Lambda가 뭔지 한 문장으로 설명해줘."}]}
    ],
    inferenceConfig={"maxTokens": 100}
)

print("응답: ", end="", flush=True)
for event in stream3["stream"]:
    if "contentBlockDelta" in event:
        print(event["contentBlockDelta"]["delta"]["text"], end="", flush=True)
    elif "metadata" in event:
        # metadata 이벤트에 토큰 사용량과 지연시간 정보가 담겨 있음
        usage = event["metadata"].get("usage", {})
        latency = event["metadata"].get("metrics", {})
        print(f"\n\n[토큰 사용량]")
        print(f"  입력 토큰: {usage.get('inputTokens', 'N/A')}")
        print(f"  출력 토큰: {usage.get('outputTokens', 'N/A')}")
        print(f"  전체 토큰: {usage.get('totalTokens', 'N/A')}")
        print(f"  지연시간:  {latency.get('latencyMs', 'N/A')} ms")

print()
print("✅ 스트리밍 테스트 완료!")