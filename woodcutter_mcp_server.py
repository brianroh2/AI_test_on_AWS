"""
woodcutter_mcp_server.py
────────────────────────────────────────────────────────────────────
P6_09 에서 사용하는 FastMCP 나무꾼 서버

stdio 모드로 실행됩니다 (MCPClient가 subprocess로 호출).
직접 실행하지 않습니다.
────────────────────────────────────────────────────────────────────
"""

from fastmcp import FastMCP

mcp = FastMCP("woodcutter")


@mcp.tool()
def chop_wood(tree_type: str, count: int = 1) -> str:
    """나무를 벤다.

    Args:
        tree_type: 나무 종류 (oak, pine, birch 등)
        count: 벨 나무 수량
    """
    return f"{tree_type} 나무 {count}그루를 베었습니다! 🪓"


@mcp.tool()
def make_lumber(log_count: int) -> str:
    """통나무를 목재로 가공한다.

    Args:
        log_count: 가공할 통나무 수량
    """
    planks = log_count * 4
    return f"통나무 {log_count}개로 목재 {planks}개를 만들었습니다! 🪵"


@mcp.tool()
def sell_lumber(lumber_count: int, price_per_unit: int = 100) -> str:
    """목재를 판매한다.

    Args:
        lumber_count: 판매할 목재 수량
        price_per_unit: 목재 1개당 가격 (기본값 100원)
    """
    total = lumber_count * price_per_unit
    return f"목재 {lumber_count}개를 {price_per_unit}원에 팔아 총 {total:,}원 벌었습니다! 💰"


if __name__ == "__main__":
    mcp.run(transport="stdio")
