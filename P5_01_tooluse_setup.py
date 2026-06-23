"""
P5_01_tooluse_setup.py
────────────────────────────────────────────────────────────────────
Tool Use 챕터 01 — 환경, 모델, 도구 확인

01-1. boto3 환경 및 모델 확인
01-2. wttr.in 외부 접근 테스트 (Tool Use에서 사용)

실행:
  python3 P5_01_tooluse_setup.py
────────────────────────────────────────────────────────────────────
"""

import boto3
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error   import URLError, HTTPError

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
sts     = boto3.client("sts",             region_name=REGION)

print("=" * 55)
print("  Part 5 — Tool Use 사전 환경 확인")
print("=" * 55)

# 01-1. 환경 확인
print(f"\n[01-1] 환경 확인")
identity = sts.get_caller_identity()
print(f"  ARN   : {identity['Arn']}")
print(f"  리전  : {REGION}")
print(f"  모델  : {MODEL_ID}")

# 모델 동작 확인
try:
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": "ping"}]}],
        inferenceConfig={"maxTokens": 10},
    )
    print(f"  ✅ 모델 호출 성공")
except Exception as e:
    print(f"  ❌ 모델 호출 실패: {e}")

# toolConfig 지원 모델 안내
print(f"""
  Tool Use 지원 모델:
    ✅ Claude (Opus / Sonnet / Haiku)
    ✅ Amazon Nova (Pro / Lite / Micro)
    ❌ Titan / Stable Diffusion 등은 미지원
    ⚠️  toolConfig 전달 시 미지원 모델 → ValidationException
""")

# 01-2. wttr.in 외부 접근 테스트
print(f"[01-2] wttr.in 외부 날씨 API 접근 테스트")
cities = ["Seoul", "Tokyo", "New York"]
for city in cities:
    try:
        url = f"https://wttr.in/{quote(city)}?format=3"
        req = Request(url, headers={"User-Agent": "curl/8"})
        with urlopen(req, timeout=8) as resp:
            report = resp.read().decode("utf-8").strip()
        print(f"  ✅ {city:12s}: {report}")
    except (URLError, HTTPError) as e:
        print(f"  ❌ {city:12s}: 접근 실패 — {e}")

print(f"""
  format=3 결과 형식:
    Seoul: ☀️  +28°C
    (도시명: 날씨아이콘 온도)

  ⚠️  접근 실패 시 P5_03~P5_06의 get_weather()가 동작하지 않습니다.
      → SageMaker 아웃바운드 443 포트 허용 여부 확인 필요

""")
print("=" * 55)
print("  환경 확인 완료 → P5_02 로 진행하세요")
print("=" * 55)
