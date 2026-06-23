"""
bedrock_06_pdf_reader.py
────────────────────────────────────────────────────────────────────
주제: Bedrock Multimodal — PDF 페이지를 이미지로 변환 후 Claude로 읽기

PDF 텍스트 직접 추출은 한국어 PDF 인코딩 문제로 깨짐.
→ PDF 페이지 → PNG 이미지 → Bedrock Claude 멀티모달로 해결.

기능:
  - 단일 페이지 읽기 (페이지 번호 지정)
  - 범위 읽기 (예: 80~85페이지 → 챕터 요약)
  - 대화형 모드: 질문을 입력하면 해당 페이지에서 답변

의존 패키지:
  pip install pymupdf  (이미 설치됨)

실행:
  python3 bedrock_06_pdf_reader.py                   # 기본 데모
  python3 bedrock_06_pdf_reader.py --page 80         # 단일 페이지
  python3 bedrock_06_pdf_reader.py --from 80 --to 85 # 범위
  python3 bedrock_06_pdf_reader.py --chat             # 대화형 모드
────────────────────────────────────────────────────────────────────
"""

import argparse
import boto3
import fitz  # pymupdf

REGION   = "us-east-1"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
PDF_PATH = "Agent_AI_개발실습.pdf"
DPI      = 150   # 해상도 (높을수록 선명하지만 용량 증가)

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
SEP     = "─" * 60


# ═══════════════════════════════════════════════════════════════
# 핵심 함수: PDF 페이지 → PNG bytes
# ═══════════════════════════════════════════════════════════════
def page_to_image(doc: fitz.Document, page_num: int) -> bytes:
    """1-indexed 페이지 번호를 받아 PNG bytes 반환"""
    page = doc[page_num - 1]
    pix  = page.get_pixmap(dpi=DPI)
    return pix.tobytes("png")


# ═══════════════════════════════════════════════════════════════
# 단일 페이지 읽기
# ═══════════════════════════════════════════════════════════════
def read_page(doc: fitz.Document, page_num: int,
              question: str = "이 페이지를 한국어로 요약하고, 코드가 있으면 코드도 포함하세요.") -> str:
    img = page_to_image(doc, page_num)
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{
            "role": "user",
            "content": [
                {"image": {"format": "png", "source": {"bytes": img}}},
                {"text": question},
            ],
        }],
        inferenceConfig={"maxTokens": 1000},
    )
    return resp["output"]["message"]["content"][0]["text"].strip()


# ═══════════════════════════════════════════════════════════════
# 범위 읽기 — 각 페이지를 순서대로 요약
# ═══════════════════════════════════════════════════════════════
def read_range(doc: fitz.Document, from_page: int, to_page: int,
               question: str = "이 페이지의 핵심 내용을 3줄 이내로 요약하세요.") -> None:
    total = doc.page_count
    to_page = min(to_page, total)
    print(f"\n  PDF: {PDF_PATH}  ({total}페이지)")
    print(f"  읽기 범위: {from_page}~{to_page}페이지")
    print(f"  질문: {question}\n")

    for p in range(from_page, to_page + 1):
        print(f"{SEP}")
        print(f"  📄 {p}페이지")
        print(SEP)
        summary = read_page(doc, p, question)
        print(summary)
        print()


# ═══════════════════════════════════════════════════════════════
# 대화형 모드 — 페이지 지정 후 자유 질문
# ═══════════════════════════════════════════════════════════════
def chat_mode(doc: fitz.Document) -> None:
    total = doc.page_count
    print(f"\n  PDF 대화 모드 (총 {total}페이지)")
    print(f"  종료: 'q' 입력\n")

    current_page = None
    history = []   # 멀티턴 대화 유지

    while True:
        user_input = input("  > ").strip()
        if user_input.lower() in ("q", "quit", "exit"):
            print("  종료합니다.")
            break
        if not user_input:
            continue

        # 페이지 이동 명령: "p 80" or ":80"
        if user_input.startswith("p ") or user_input.startswith(":"):
            try:
                num_str = user_input.replace("p ", "").replace(":", "")
                p = int(num_str)
                if 1 <= p <= total:
                    current_page = p
                    history = []   # 페이지 변경 시 히스토리 초기화
                    print(f"  📄 {current_page}페이지로 이동 (히스토리 초기화)\n")
                else:
                    print(f"  페이지 범위: 1~{total}")
                continue
            except ValueError:
                pass

        if current_page is None:
            # 페이지 미지정 시 자동으로 질문
            try:
                p = int(input(f"  읽을 페이지 번호 (1~{total}): ").strip())
                current_page = p
            except ValueError:
                print("  숫자를 입력하세요.")
                continue

        # 현재 페이지 이미지 준비
        img = page_to_image(doc, current_page)

        # 멀티턴: 이전 대화 + 현재 질문
        new_msg = {
            "role": "user",
            "content": [
                {"image": {"format": "png", "source": {"bytes": img}}},
                {"text": user_input},
            ],
        }
        history.append(new_msg)

        resp = bedrock.converse(
            modelId=MODEL_ID,
            system=[{"text": (
                "당신은 PDF 문서 분석 어시스턴트입니다. "
                "제공된 페이지 이미지를 보고 질문에 정확하게 답하세요. "
                "코드가 있으면 마크다운 코드 블록으로 표시하세요."
            )}],
            messages=history,
            inferenceConfig={"maxTokens": 1000},
        )
        answer = resp["output"]["message"]["content"][0]["text"].strip()
        history.append({"role": "assistant", "content": [{"text": answer}]})

        print(f"\n  [📄 {current_page}페이지]\n{answer}\n")
        print(f"  (현재 페이지: {current_page} | 변경: 'p <번호>' | 종료: q)")


# ═══════════════════════════════════════════════════════════════
# 기본 데모 — 주요 챕터 페이지 미리보기
# ═══════════════════════════════════════════════════════════════
def demo(doc: fitz.Document) -> None:
    print(f"\n{SEP}")
    print("  기본 데모: 챕터 대표 페이지 요약")
    print(SEP)

    # 강의 자료의 주요 챕터 대표 페이지
    demos = [
        (80, "11. Bedrock Prompt Management"),
        (82, "12. Intelligent Prompt Routing"),
        (85, "13. Prompt Caching"),
        (87, "14. Prompt Optimization"),
    ]

    for page_num, title in demos:
        print(f"\n  ── {title} (p.{page_num}) ──")
        summary = read_page(
            doc, page_num,
            "이 페이지의 핵심 내용을 3줄 이내로 요약하세요. 코드가 있으면 첫 번째 코드 예제만 보여주세요."
        )
        print(summary)


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bedrock PDF Reader")
    parser.add_argument("--page",  type=int, help="읽을 페이지 번호 (1-indexed)")
    parser.add_argument("--from",  dest="from_page", type=int, help="범위 시작 페이지")
    parser.add_argument("--to",    dest="to_page",   type=int, help="범위 끝 페이지")
    parser.add_argument("--chat",  action="store_true",         help="대화형 모드")
    parser.add_argument("--pdf",   default=PDF_PATH,            help="PDF 파일 경로")
    parser.add_argument("--question", default=None,             help="단일 페이지 질문")
    args = parser.parse_args()

    print("=" * 60)
    print(" bedrock_06_pdf_reader.py")
    print(" Bedrock Multimodal PDF 리더")
    print("=" * 60)

    doc = fitz.open(args.pdf)
    print(f"\n  PDF 로드: {args.pdf}  ({doc.page_count}페이지)")
    print(f"  페이지 이동: 'p <번호>' | 종료: q")

    try:
        if args.chat:
            chat_mode(doc)

        elif args.page:
            q = args.question or "이 페이지를 한국어로 요약하고, 코드가 있으면 코드도 포함하세요."
            print(f"\n  📄 {args.page}페이지  질문: {q}\n")
            print(read_page(doc, args.page, q))

        elif args.from_page and args.to_page:
            q = args.question or "이 페이지의 핵심 내용을 3줄 이내로 요약하세요."
            read_range(doc, args.from_page, args.to_page, q)

        else:
            demo(doc)

    finally:
        doc.close()

    print(f"\n{'=' * 60}")
    print("완료")
    print("=" * 60)
