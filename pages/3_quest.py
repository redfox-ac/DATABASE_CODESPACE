import streamlit as st

from utils.auth import require_login
from utils.db import fetch_quests

st.set_page_config(page_title="퀘스트 · EcoQuest", layout="wide")
require_login()

st.title("🎯 퀘스트 보드")

quests = fetch_quests()

if not quests:
    st.info("진행 가능한 퀘스트가 없습니다.")
    st.stop()

for quest in quests:
    with st.container(border=True):
        q_col1, q_col2 = st.columns([3, 1])
        with q_col1:
            st.markdown(f"### 퀘스트 #{quest['id']}")
            st.write(quest.get("description") or "설명 없음")
        with q_col2:
            st.metric("보상 XP", f"+{quest.get('reward_xp', 0)}")
            st.button(
                "보상 수령",
                key=f"claim_{quest['id']}",
                disabled=True,
                help="보상 수령 기능은 준비 중입니다.",
            )
