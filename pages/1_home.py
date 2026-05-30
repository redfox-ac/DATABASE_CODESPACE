import random

import streamlit as st

from utils.auth import require_login
from utils.db import (
    fetch_dictionary_ids,
    fetch_user,
    insert_discovery_transaction,
)

st.set_page_config(page_title="홈 · EcoQuest", layout="wide")
require_login()

user = st.session_state.user_info
fresh = fetch_user(user["id"], nickname=user.get("nickname", ""))
if fresh:
    st.session_state.user_info = fresh
    user = fresh


@st.dialog("📸 생물 수집 렌즈")
def collection_lens():
    st.markdown("촬영한 생물 사진을 업로드해 주세요.")
    uploaded = st.file_uploader(
        "이미지 선택",
        type=["jpg", "jpeg", "png", "webp"],
        key="collection_upload",
    )
    if uploaded is None:
        return

    dict_ids = fetch_dictionary_ids()
    if not dict_ids:
        st.info("등록 가능한 도감 데이터가 없습니다.")
        return

    chosen_id = random.choice(dict_ids)
    result = insert_discovery_transaction(user["id"], chosen_id)

    if result is None:
        return
    if result.get("duplicate"):
        st.info("이미 수집한 생물입니다.")
        return

    entry = result
    name = entry.get("name", "알 수 없는 생물")
    if entry.get("is_protected"):
        st.warning(
            f"⚠️ **{name}** — 법정 보호종으로 확인되었습니다. "
            "관찰 기록만 저장되며, 채집·포획은 금지됩니다. (+10 XP)"
        )
    else:
        st.success(f"🎉 **{name}** 수집 완료! (+10 XP)")

    updated = fetch_user(user["id"], nickname=user.get("nickname", ""))
    if updated:
        st.session_state.user_info = updated
    st.rerun()


st.title("🏠 대시보드")

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("닉네임", user["nickname"])
with col_b:
    st.metric("신뢰도", f"{user.get('trust_score', 0)} pt")
with col_c:
    xp = user.get("xp", 0)
    max_xp = user.get("max_xp", 200) or 200
    st.metric("경험치", f"{xp} / {max_xp}")

progress = min(xp / max_xp, 1.0) if max_xp > 0 else 0.0
st.progress(progress, text=f"레벨 진행도 {int(progress * 100)}%")

st.divider()
st.subheader("생물 수집")
st.caption("사진을 업로드하면 AI 렌즈가 생물을 분석해 도감에 등록합니다. (데모: 랜덤 종 선택)")

if st.button("📸 생물 수집 렌즈 열기", type="primary"):
    collection_lens()
