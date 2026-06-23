"""
P6_01_strands_setup.py
────────────────────────────────────────────────────────────────────
Strands 챕터 01 — 환경, 패키지, 기본 Agent 확인

01-1. 패키지 설치 확인 (strands-agents, strands-agents-tools, requests)
01-2. boto3 Session + BedrockModel 확인

실행:
  python3 P6_01_strands_setup.py
────────────────────────────────────────────────────────────────────
"""

import boto3
import subprocess
import sys

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

print("=" * 60)
print("  Part 6 — Strands Agentic AI 사전 환경 확인")
print("=" * 60)

# ── 01-1. 패키지 버전 확인 ───────────────────────────────────────
print("\n[01-1] 패키지 버전 확인")
pkgs = ["strands-agents", "strands-agents-tools", "boto3", "requests"]
result = subprocess.run(
    [sys.executable, "-m", "pip", "list"],
    capture_output=True, text=True
)
installed = {}
for line in result.stdout.splitlines():
    parts = line.split()
    if len(parts) >= 2:
        installed[parts[0].lower()] = parts[1]

for pkg in pkgs:
    ver = installed.get(pkg.lower(), "미설치")
    icon = "✅" if ver != "미설치" else "❌"
    print(f"  {icon} {pkg:30s}: {ver}")

# strands import 테스트
print("\n  import 테스트:")
try:
    from strands import Agent, tool
    from strands.models import BedrockModel
    print("  ✅ from strands import Agent, tool, BedrockModel")
except ImportError as e:
    print(f"  ❌ strands import 실패: {e}")
    print("     → !pip install -qU strands-agents strands-agents-tools boto3 requests")

try:
    from strands_tools import calculator
    print("  ✅ from strands_tools import calculator")
except ImportError as e:
    print(f"  ❌ strands_tools import 실패: {e}")

# ── 01-2. boto3 Session + BedrockModel ───────────────────────────
print("\n[01-2] boto3 Session + BedrockModel 확인")

try:
    from strands import Agent
    from strands.models import BedrockModel

    session = boto3.Session(region_name=REGION)
    print(f"  ARN  : {session.client('sts').get_caller_identity()['Arn']}")
    print(f"  리전 : {session.region_name}")

    # BedrockModel 생성
    model = BedrockModel(
        model_id=MODEL_ID,
        boto_session=session,
        streaming=True,
    )
    print(f"  모델 : {MODEL_ID}")

    # 간단한 Agent 호출 테스트
    agent = Agent(model=model)
    result = agent("안녕! 한 줄로 짧게 대답해줘.")
    print(f"  ✅ Agent 응답: {str(result)[:80]}")

except Exception as e:
    print(f"  ❌ 오류: {e}")

print(f"""
  ─────────────────────────────────────────────
  Strands 핵심 구조:

  BedrockModel(model_id=..., boto_session=...)
      ↓
  Agent(model=...)
      ↓
  agent("질문")  →  스트리밍 출력

  Strands는 boto3 IAM 권한으로 동작합니다.
  AWS 액세스 키 불필요 (SageMaker IAM Role 활용)

  ⚠️  주의:
    ModuleNotFoundError → pip install strands-agents (1회)
    AccessDeniedException → bedrock:InvokeModel 권한 확인
    list-inference-profiles → us-east-1 / us-west-2 필요
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P6_01 완료 → P6_02 로 진행하세요")
print("=" * 60)
