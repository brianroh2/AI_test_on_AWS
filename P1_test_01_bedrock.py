import boto3

REGION = "us-east-1"
# 목록에 있는 모델에 us. 접두사 붙임
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)

# ── 샘플 1: 단순 1회 호출 ─────────────────────
print("=" * 50)
print("샘플 1: 단순 호출")
print("=" * 50)

response = bedrock.converse(
    modelId=MODEL_ID,
    messages=[
        {"role": "user", "content": [{"text": "안녕! 한 줄로 자기소개해줘."}]}
    ],
    inferenceConfig={"maxTokens": 200, "temperature": 0.7}
)
print("응답:", response["output"]["message"]["content"][0]["text"])
print()

# ── 샘플 2: 시스템 프롬프트 ──────────────────
print("=" * 50)
print("샘플 2: 시스템 프롬프트 적용")
print("=" * 50)

response2 = bedrock.converse(
    modelId=MODEL_ID,
    system=[{"text": "당신은 친절한 AWS 전문가입니다. 항상 한국어로 답변하세요."}],
    messages=[
        {"role": "user", "content": [{"text": "Amazon Bedrock이 뭔지 2줄로 설명해줘."}]}
    ],
    inferenceConfig={"maxTokens": 300}
)
print("응답:", response2["output"]["message"]["content"][0]["text"])
print()

# ── 샘플 3: 멀티턴 대화 ──────────────────────
print("=" * 50)
print("샘플 3: 멀티턴 대화 (이름 기억 테스트)")
print("=" * 50)

history = []

def chat(user_input):
    history.append({"role": "user", "content": [{"text": user_input}]})
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=history,
        inferenceConfig={"maxTokens": 300}
    )
    reply = resp["output"]["message"]["content"][0]["text"]
    history.append({"role": "assistant", "content": [{"text": reply}]})
    return reply

q1 = "내 이름은 KW야."
print(f"사용자: {q1}")
print(f"Claude: {chat(q1)}\n")

q2 = "내 이름이 뭐라고 했지?"
print(f"사용자: {q2}")
print(f"Claude: {chat(q2)}\n")

print("✅ 모든 테스트 완료!")
