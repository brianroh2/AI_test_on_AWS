"""
P6_06_strands_stat.py
────────────────────────────────────────────────────────────────────
Strands 챕터 06 — 실행 통계 (Metrics)

06-1. 기본 Agent 호출 후 accumulated_usage 확인
06-2. cycle_durations 확인
06-3. 도구 사용 후 tool_metrics 확인
06-4. get_summary() 전체 통계 출력

실행:
  python3 P6_06_strands_stat.py
────────────────────────────────────────────────────────────────────
"""

import boto3
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator

REGION   = "us-east-1"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

session = boto3.Session(region_name=REGION)

model = BedrockModel(
    model_id=MODEL_ID,
    boto_session=session,
    streaming=False,
)

print("=" * 60)
print("  Part 6 — 실행 통계 (Metrics)")
print("=" * 60)

# ── 06-1. accumulated_usage ───────────────────────────────────────
print("\n[06-1] accumulated_usage — 토큰 사용량")

agent = Agent(model=model, callback_handler=None)
result = agent("AWS Bedrock이란 무엇인지 한 줄로 설명해줘.")

usage = result.metrics.accumulated_usage
print(f"  입력 토큰  : {usage.get('inputTokens', 0):>6,}")
print(f"  출력 토큰  : {usage.get('outputTokens', 0):>6,}")
print(f"  총 토큰    : {usage.get('totalTokens', 0):>6,}")

# ── 06-2. cycle_durations ─────────────────────────────────────────
print("\n[06-2] cycle_durations — 사이클별 소요 시간")

durations = result.metrics.cycle_durations
for i, d in enumerate(durations, 1):
    print(f"  Cycle {i}: {d:.3f}초")
print(f"  합계     : {sum(durations):.3f}초")

# ── 06-3. tool_metrics ────────────────────────────────────────────
print("\n[06-3] tool_metrics — 도구 사용 통계")

agent_tool = Agent(model=model, tools=[calculator], callback_handler=None)
result_tool = agent_tool("456 * 789 계산해줘")

tool_metrics = result_tool.metrics.tool_metrics
if tool_metrics:
    for name, tm in tool_metrics.items():
        print(f"  도구 이름  : {name}")
        print(f"  호출 횟수  : {tm.call_count}")
        print(f"  성공 횟수  : {tm.success_count}")
        print(f"  오류 횟수  : {tm.error_count}")
        print(f"  총 소요    : {tm.total_time:.4f}초")
else:
    print("  (도구 미사용)")

# ── 06-4. get_summary() ───────────────────────────────────────────
print("\n[06-4] get_summary() — 전체 통계 요약")

summary = result_tool.metrics.get_summary()
print(f"  총 사이클  : {summary['total_cycles']}")
print(f"  총 소요    : {summary['total_duration']:.3f}초")
print(f"  평균 사이클: {summary['average_cycle_time']:.3f}초")
print(f"  토큰 사용  : {result_tool.metrics.accumulated_usage}")

if summary.get("tool_usage"):
    print(f"  도구 통계  :")
    for t_name, t_stat in summary["tool_usage"].items():
        es = t_stat["execution_stats"]
        print(f"    [{t_name}] 호출={es['call_count']} 성공={es['success_count']}"
              f" 성공률={es['success_rate']:.0%} 평균={es['average_time']:.4f}초")

print(f"""
  ─────────────────────────────────────────────
  Strands Metrics 핵심:
    • result.metrics.accumulated_usage
        → inputTokens / outputTokens / totalTokens
    • result.metrics.cycle_durations
        → 각 LLM 호출 사이클별 소요 시간 (초)
    • result.metrics.tool_metrics
        → 도구별 call_count / success_count / total_time
    • result.metrics.get_summary()
        → 전체 요약 딕셔너리 (사이클, 시간, 도구 통계)

  ⚠️  주의:
    • callback_handler=None 으로 출력 억제 후 result 캡처
    • tool_metrics 는 도구를 사용한 경우에만 채워짐
  ─────────────────────────────────────────────
""")
print("=" * 60)
print("  P6_06 완료 → P6_07 로 진행하세요")
print("=" * 60)
