"""
pdf_viewer.py  —  Streamlit PDF 뷰어
실행: streamlit run pdf_viewer.py --server.port 8502 --server.headless true &
접속: VS Code Ports 탭 → 8502 포워딩
"""

import streamlit as st
import fitz  # pymupdf
from pathlib import Path

PDF_PATH = "Agent_AI_개발실습.pdf"

st.set_page_config(page_title="PDF 뷰어", page_icon="📄", layout="wide")
st.title("📄 PDF 뷰어")

doc = fitz.open(PDF_PATH)
total = doc.page_count

col1, col2, col3 = st.columns([2, 3, 2])
with col1:
    page_num = st.number_input("페이지", min_value=1, max_value=total,
                               value=1, step=1)
with col2:
    st.caption(f"총 {total}페이지")
with col3:
    dpi = st.select_slider("해상도", options=[100, 150, 200], value=150)

page = doc[page_num - 1]
pix  = page.get_pixmap(dpi=dpi)
st.image(pix.tobytes("png"), use_container_width=True)

doc.close()
