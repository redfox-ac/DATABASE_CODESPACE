import streamlit as st

from utils.auth import require_login
from utils.db import fetch_all_categories, fetch_paged_dictionary_with_discovery

PLACEHOLDER_IMAGE = "https://dummyimage.com/300x200/cccccc/666666&text=No+Image"

st.set_page_config(page_title="도감 · EcoQuest", layout="wide")
require_login()

user = st.session_state.user_info

@st.dialog("🔍 생물 상세 정보")
def show_details(item):
    st.subheader(item["name"])
    
    image_url = item.get("image_url") or PLACEHOLDER_IMAGE
    st.image(image_url, use_container_width=True)
    
    is_protected = bool(item.get("is_protected"))
    is_discovered = bool(item.get("image_url"))
    
    badge_col1, badge_col2 = st.columns(2)
    with badge_col1:
        if is_protected:
            st.markdown("⚠️ **법정 보호종**")
        else:
            st.markdown("🌿 **일반종**")
    with badge_col2:
        if is_discovered:
            st.markdown("✅ **발견 완료** (+10 XP)")
        else:
            st.markdown("🔒 **미발견**")
            
    st.divider()
    st.markdown("### 생물 설명")
    st.write(item.get("description") or "설명이 등록되지 않았습니다.")


st.title("📖 생물 도감")

# Fetch categories and prepare options
db_categories = fetch_all_categories()
category_options = ["전체"] + [c["name"] for c in db_categories]
category_name_to_id = {c["name"]: c["id"] for c in db_categories}

# Filters
filter_col1, filter_col2, filter_col3 = st.columns(3)
with filter_col1:
    search_name = st.text_input("이름 검색", placeholder="생물 이름 입력...")
with filter_col2:
    category_filter = st.selectbox("분류 필터", category_options)
with filter_col3:
    discovery_filter = st.selectbox("발견 여부 필터", ["전체", "발견 완료", "미발견"], index=1)

selected_category_id = category_name_to_id.get(category_filter)

# Filter state checks to reset page
if "prev_search" not in st.session_state:
    st.session_state.prev_search = ""
if "prev_category" not in st.session_state:
    st.session_state.prev_category = "전체"
if "prev_discovery" not in st.session_state:
    st.session_state.prev_discovery = "전체"
if "dictionary_page" not in st.session_state:
    st.session_state.dictionary_page = 1

if (search_name != st.session_state.prev_search or 
    category_filter != st.session_state.prev_category or 
    discovery_filter != st.session_state.prev_discovery):
    st.session_state.dictionary_page = 1
    st.session_state.prev_search = search_name
    st.session_state.prev_category = category_filter
    st.session_state.prev_discovery = discovery_filter

# Fetch paged data
limit = 24
offset = (st.session_state.dictionary_page - 1) * limit

paged_data, total_count = fetch_paged_dictionary_with_discovery(
    user_id=user["id"],
    search_query=search_name,
    # pyrefly: ignore [bad-argument-type]
    category_id=selected_category_id,
    discovery_filter=discovery_filter,
    limit=limit,
    offset=offset
)

if total_count == 0:
    st.info("조건에 맞는 생물이 없습니다.")
    st.stop()

st.caption(f"총 {total_count}종 표시 중 (현재 페이지: {st.session_state.dictionary_page})")

cols_per_row = 3
for i in range(0, len(paged_data), cols_per_row):
    cols = st.columns(cols_per_row)
    for col, item in zip(cols, paged_data[i : i + cols_per_row]):
        with col:
            image_url = item.get("image_url") or PLACEHOLDER_IMAGE
            is_protected = bool(item.get("is_protected"))
            name = item.get("name", "이름 없음")
            
            with st.container(border=True):
                if is_protected:
                    st.markdown("<span style='color: #e63946; font-weight: bold;'>⚠️ 법정 보호종</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='color: #2d6a4f; font-weight: bold;'>🌿 일반종</span>", unsafe_allow_html=True)
                    
                st.image(image_url, use_container_width=True)
                st.markdown(f"**{name}**")
                
                if st.button("자세히 보기", key=f"details_{item['dictionary_id']}", use_container_width=True):
                    show_details(item)

# Pagination UI
st.divider()
total_pages = (total_count - 1) // limit + 1 if total_count > 0 else 1

page_col1, page_col2, page_col3 = st.columns([1, 2, 1])
with page_col1:
    if st.button("이전 페이지", disabled=(st.session_state.dictionary_page <= 1), use_container_width=True):
        st.session_state.dictionary_page -= 1
        st.rerun()
with page_col2:
    st.markdown(
        f"<div style='text-align: center; line-height: 2.2;'>페이지 <b>{st.session_state.dictionary_page}</b> / {total_pages} (총 {total_count}종)</div>",
        unsafe_allow_html=True
    )
with page_col3:
    if st.button("다음 페이지", disabled=(st.session_state.dictionary_page >= total_pages), use_container_width=True):
        st.session_state.dictionary_page += 1
        st.rerun()
