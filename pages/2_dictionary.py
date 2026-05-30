import streamlit as st

from utils.auth import require_login
from utils.db import fetch_user_collection

PLACEHOLDER_IMAGE = "https://dummyimage.com/300x200/cccccc/666666&text=No+Image"

st.set_page_config(page_title="도감 · EcoQuest", layout="wide")
require_login()

user = st.session_state.user_info
collection = fetch_user_collection(user["id"])

st.title("📖 생물 도감")

if not collection:
    st.info("아직 수집한 생물이 없습니다. 홈에서 수집 렌즈로 탐험을 시작해 보세요!")
    st.stop()

categories = sorted({str(item["category_id"]) for item in collection if item.get("category_id") is not None})
category_options = ["전체"] + categories

filter_col1, filter_col2 = st.columns(2)
with filter_col1:
    search_name = st.text_input("이름 검색", placeholder="생물 이름 입력...")
with filter_col2:
    category_filter = st.selectbox("분류 필터", category_options)

filtered = collection
if search_name.strip():
    q = search_name.strip().lower()
    filtered = [item for item in filtered if q in (item.get("name") or "").lower()]
if category_filter != "전체":
    filtered = [
        item for item in filtered if str(item.get("category_id")) == category_filter
    ]

if not filtered:
    st.info("조건에 맞는 생물이 없습니다.")
    st.stop()

st.caption(f"총 {len(filtered)}종 표시 중")

cols_per_row = 3
for i in range(0, len(filtered), cols_per_row):
    cols = st.columns(cols_per_row)
    for col, item in zip(cols, filtered[i : i + cols_per_row]):
        with col:
            image_url = item.get("image_url") or PLACEHOLDER_IMAGE
            is_protected = bool(item.get("is_protected"))
            name = item.get("name", "이름 없음")
            desc = item.get("description") or "설명 없음"

            if is_protected:
                st.markdown(
                    """
                    <div style="border: 3px solid #e63946; border-radius: 8px; padding: 4px;">
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown("### 🛡️ 법정 보호종")

            st.image(image_url, use_container_width=True)
            st.markdown(f"**{name}**")
            st.caption(desc[:120] + ("…" if len(desc) > 120 else ""))

            if is_protected:
                st.markdown("</div>", unsafe_allow_html=True)
