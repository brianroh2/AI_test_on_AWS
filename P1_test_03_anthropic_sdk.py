# ============================================================
# 파일명: P1_test_03_anthropic_sdk.py
# 주제: Anthropic SDK(AnthropicBedrock)로 Bedrock Claude 호출
#
# 【이 코드가 하는 일】
#   boto3의 bedrock-runtime 대신 Anthropic이 직접 제공하는
#   Python SDK를 사용해 Bedrock 위의 Claude를 호출합니다.
#
# 【boto3 방식과의 차이】
#   boto3 방식  : AWS 네이티브, 다양한 공급사 모델 통일 호출
#   Anthropic SDK: Claude 전용, Claude API와 거의 동일한 코드
#                  → 기존 Claude API 코드를 Bedrock으로 이전 시 유리
#
# 【실습 구성】
#   샘플 1: AnthropicBedrock 클라이언트 생성 및 기본 호출
#   샘플 2: boto3 방식과 Anthropic SDK 방식 나란히 비교
#   샘플 3: Anthropic SDK로 스트리밍
#   샘플 4: Anthropic SDK로 멀티턴 대화
#   샘플 5: 시스템 프롬프트 + 멀티턴 조합
# ============================================================

import boto3
import anthropic
from anthropic import AnthropicBedrock

# ── 공통 설정 ────────────────────────────────────────────────
REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"


# ============================================================
# 샘플 1: AnthropicBedrock 클라이언트 생성 및 기본 호출
#
# AnthropicBedrock()은 AWS 자격증명을 자동으로 읽습니다.
# SageMaker IAM Role이 있으므로 키 설정 없이 바로 사용 가능합니다.
# messages.create()는 Anthropic Claude API와 동일한 형식입니다.
# ============================================================
print("=" * 55)
print("샘플 1: AnthropicBedrock 기본 호출")
print("=" * 55)

# AnthropicBedrock 클라이언트 생성
# aws_region: 호출할 Bedrock 리전 지정
client = AnthropicBedrock(aws_region=REGION)

# messages.create()로 모델 호출
# boto3의 converse()와 역할은 같지만 파라미터 형식이 다름
response = client.messages.create(
    model=MODEL_ID,
    max_tokens=200,
    messages=[
        {"role": "user", "content": "안녕! 한 줄로 자기소개해줘."}
        # boto3: [{"text": "..."}] 리스트 형식
        # Anthropic SDK: 문자열 직접 입력 가능
    ]
)

# 응답 텍스트 추출
# boto3: response["output"]["message"]["content"][0]["text"]
# Anthropic SDK: response.content[0].text  ← 더 간결
print("응답:", response.content[0].text)
print(f"[모델: {response.model}]")
print(f"[토큰: 입력={response.usage.input_tokens}, "
      f"출력={response.usage.output_tokens}]")
print()


# ============================================================
# 샘플 2: boto3 방식 vs Anthropic SDK 방식 나란히 비교
#
# 동일한 질문을 두 방식으로 호출하고 응답을 나란히 출력합니다.
# 코드 구조의 차이를 직접 눈으로 비교할 수 있습니다.
# ============================================================
print("=" * 55)
print("샘플 2: boto3 vs Anthropic SDK 비교")
print("=" * 55)

QUESTION = "AWS S3가 뭔지 한 문장으로 설명해줘."

# ── boto3 방식 ──────────────────────────────────
bedrock_boto3 = boto3.client("bedrock-runtime", region_name=REGION)

boto3_response = bedrock_boto3.converse(
    modelId=MODEL_ID,
    messages=[
        # boto3: content가 리스트 + dict 형식
        {"role": "user", "content": [{"text": QUESTION}]}
    ],
    inferenceConfig={"maxTokens": 150}
)
boto3_answer = boto3_response["output"]["message"]["content"][0]["text"]

# ── Anthropic SDK 방식 ──────────────────────────
sdk_response = client.messages.create(
    model=MODEL_ID,
    max_tokens=150,
    messages=[
        # Anthropic SDK: content가 문자열 직접 가능
        {"role": "user", "content": QUESTION}
    ]
)
sdk_answer = sdk_response.content[0].text

# 나란히 출력
print(f"질문: {QUESTION}\n")
print(f"[boto3 응답]\n  {boto3_answer}\n")
print(f"[Anthropic SDK 응답]\n  {sdk_answer}\n")
print("→ 같은 모델, 같은 질문 → 비슷한 답변 / 코드 형식만 다름")
print()


# ============================================================
# 샘플 3: Anthropic SDK로 스트리밍
#
# with client.messages.stream() 컨텍스트 매니저를 사용합니다.
# boto3의 converse_stream()과 역할은 같지만 문법이 더 간결합니다.
# ============================================================
print("=" * 55)
print("샘플 3: Anthropic SDK 스트리밍")
print("=" * 55)

print("응답: ", end="", flush=True)

# with 블록으로 스트림 자동 관리 (boto3보다 간결)
with client.messages.stream(
    model=MODEL_ID,
    max_tokens=300,
    messages=[
        {"role": "user", "content": "파이썬과 자바의 차이를 3줄로 설명해줘."}
    ]
) as stream:
    # text_stream: 텍스트 조각만 자동으로 추출해서 순회
    for text_chunk in stream.text_stream:
        print(text_chunk, end="", flush=True)

print("\n")


# ============================================================
# 샘플 4: Anthropic SDK로 멀티턴 대화
#
# boto3 방식과 동일하게 history 리스트를 누적합니다.
# 차이점은 content 형식이 문자열이라는 점입니다.
# ============================================================
print("=" * 55)
print("샘플 4: Anthropic SDK 멀티턴 대화")
print("=" * 55)

history = []  # 대화 기록 저장

def sdk_chat(user_input):
    """Anthropic SDK로 멀티턴 대화하는 함수"""

    # 사용자 메시지 추가 (문자열 형식으로)
    history.append({"role": "user", "content": user_input})

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=300,
        messages=history  # 전체 history 전달 → 문맥 유지
    )

    reply = response.content[0].text

    # 모델 응답을 history에 추가
    history.append({"role": "assistant", "content": reply})

    return reply

# 대화 테스트
q1 = "내가 좋아하는 언어는 Python이야."
print(f"사용자: {q1}")
print(f"Claude: {sdk_chat(q1)}\n")

q2 = "내가 좋아하는 언어가 뭐라고 했지?"
print(f"사용자: {q2}")
print(f"Claude: {sdk_chat(q2)}\n")


# ============================================================
# 샘플 5: 시스템 프롬프트 + 멀티턴 조합
#
# system 파라미터로 모델의 역할/성격/규칙을 고정합니다.
# 시스템 프롬프트는 history에 넣지 않고 별도 파라미터로 전달합니다.
# ============================================================
print("=" * 55)
print("샘플 5: 시스템 프롬프트 + 멀티턴 조합")
print("=" * 55)

SYSTEM_PROMPT = """당신은 AWS 클라우드 전문가입니다.
- 항상 한국어로 답변하세요.
- 기술 용어는 영문(한글) 병기로 표기하세요.
- 답변은 3줄 이내로 간결하게 해주세요."""

history2 = []

def expert_chat(user_input):
    """시스템 프롬프트가 적용된 전문가 챗봇 함수"""
    history2.append({"role": "user", "content": user_input})

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=300,
        system=SYSTEM_PROMPT,   # 시스템 프롬프트 별도 전달
        messages=history2
    )

    reply = response.content[0].text
    history2.append({"role": "assistant", "content": reply})
    return reply

q1 = "EC2가 뭐야?"
print(f"사용자: {q1}")
print(f"전문가 Claude: {expert_chat(q1)}\n")

q2 = "그럼 Lambda와의 차이는?"
print(f"사용자: {q2}")
print(f"전문가 Claude: {expert_chat(q2)}\n")

q3 = "어떤 걸 언제 써야 해?"
print(f"사용자: {q3}")
print(f"전문가 Claude: {expert_chat(q3)}\n")

print("✅ Anthropic SDK 테스트 완료!")