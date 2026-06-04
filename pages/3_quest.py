import streamlit as st
from utils.auth import require_login
from utils.db import (
    fetch_available_quests,
    accept_quest,
    fetch_user_quests,
    claim_quest_reward,
    fetch_user,
    cleanup_expired_quests,
)

st.set_page_config(page_title="퀘스트 · EcoQuest", layout="wide")
require_login()

user = st.session_state.user_info
user_id = user["id"]

# Run global cleanup for expired quests
cleanup_expired_quests()

# Refresh user info to ensure XP and other stats are up to date on page load
fresh_user = fetch_user(user_id, nickname=user.get("nickname", ""))
if fresh_user:
    st.session_state.user_info = fresh_user
    user = fresh_user

st.title("🎯 퀘스트 보드")
st.caption("퀘스트를 수행하여 생태 탐사를 완료하고 특별한 보상을 획득하세요!")

# 1. Fetch user's current quests and available quests
all_user_quests = fetch_user_quests(user_id)
available_quests = fetch_available_quests(user_id)

# 2. Categorize quests into render groups
quests_to_render = []

# Group 1: Active quests (in_progress, completed)
for q in all_user_quests:
    if q["status"] in ("in_progress", "completed"):
        q["group"] = "active"
        quests_to_render.append(q)

# Group 2: Available quests (available to accept)
for q in available_quests:
    q["group"] = "available"
    q["quest_id"] = q["id"]  # Align ID keys
    quests_to_render.append(q)

# Group 3: Claimed quests (rewards already claimed, within 7 days of assigned_at - which is guaranteed by cleanup)
for q in all_user_quests:
    if q["status"] == "claimed":
        q["group"] = "claimed"
        quests_to_render.append(q)

# 3. Render integrated feed
if not quests_to_render:
    st.info("현재 표시할 퀘스트가 없습니다. 나중에 다시 확인해 주세요!")
else:
    for q in quests_to_render:
        group = q["group"]
        
        if group == "active":
            is_completed = q["status"] == "completed"
            with st.container(border=True):
                col_text, col_action = st.columns([3, 1])
                
                with col_text:
                    if is_completed:
                        st.markdown(f"### ✨ 퀘스트 #{q['quest_id']} (달성 완료!)")
                    else:
                        st.markdown(f"### 🏃 진행 중인 퀘스트 #{q['quest_id']}")
                    
                    st.markdown(f"**설명**: {q.get('description') or '설명 없음'}")
                    
                    st.markdown("**목표 달성도:**")
                    # Species targets
                    for target in q.get("target_species", []):
                        current = target["current_count"]
                        limit = target["target_count"]
                        pct = min(current / limit, 1.0) if limit > 0 else 0.0
                        st.write(f"- 🌿 **{target['species_name']}** 발견: {current} / {limit}")
                        st.progress(pct)
                        
                    # Category targets
                    for target in q.get("target_categories", []):
                        current = target["current_count"]
                        limit = target["target_count"]
                        pct = min(current / limit, 1.0) if limit > 0 else 0.0
                        st.write(f"- 📂 **{target['category_name']}** 카테고리 생물 발견: {current} / {limit}")
                        st.progress(pct)
                        
                with col_action:
                    st.subheader("보상 목록")
                    st.write(f"- 💎 **XP**: +{q.get('reward_xp', 0)}")
                    for r in q.get("rewards", []):
                        st.write(f"- 🎁 **{r['item_name']}**: {r['amount']}개")
                        
                    st.divider()
                    
                    if is_completed:
                        if st.button("🎁 보상 수령", key=f"claim_{q['quest_id']}", type="primary", use_container_width=True):
                            res = claim_quest_reward(user_id, q["quest_id"])
                            if res and res.get("success"):
                                st.balloons()
                                rewards_str = f"XP +{res['reward_xp']}"
                                if res.get("items"):
                                    rewards_str += f", {', '.join(res['items'])}"
                                st.success(f"🎉 퀘스트 보상을 성공적으로 수령했습니다! ({rewards_str})")
                                updated_user = fetch_user(user_id, nickname=user.get("nickname", ""))
                                if updated_user:
                                    st.session_state.user_info = updated_user
                                st.rerun()
                            else:
                                msg = res.get("message") if res else "오류가 발생했습니다."
                                st.error(f"❌ {msg}")
                    else:
                        st.button("진행 중...", key=f"active_{q['quest_id']}", disabled=True, use_container_width=True)
                        
        elif group == "available":
            with st.container(border=True):
                col_text, col_action = st.columns([3, 1])
                
                with col_text:
                    st.markdown(f"### 🗺️ 수락 가능한 퀘스트 #{q['quest_id']}")
                    st.markdown(f"**설명**: {q.get('description') or '설명 없음'}")
                    
                    st.markdown("**필요 목표:**")
                    if not q.get("target_species") and not q.get("target_categories"):
                        st.write("- 제한 조건 없음")
                    else:
                        for target in q.get("target_species", []):
                            st.write(f"- 🌿 **{target['species_name']}** {target['target_count']}회 관찰 및 사진 촬영")
                        for target in q.get("target_categories", []):
                            st.write(f"- 📂 **{target['category_name']}** 생물 {target['target_count']}회 관찰 및 사진 촬영")
                            
                with col_action:
                    st.subheader("예상 보상")
                    st.write(f"- 💎 **XP**: +{q.get('reward_xp', 0)}")
                    for r in q.get("rewards", []):
                        st.write(f"- 🎁 **{r['item_name']}**: {r['amount']}개")
                        
                    st.divider()
                    
                    if st.button("🎯 퀘스트 수락", key=f"accept_{q['quest_id']}", type="primary", use_container_width=True):
                        if accept_quest(user_id, q["quest_id"]):
                            st.toast(f"🎯 퀘스트 #{q['quest_id']}를 수락했습니다!")
                            st.rerun()
                            
        elif group == "claimed":
            with st.container(border=True):
                col_text, col_action = st.columns([3, 1])
                with col_text:
                    st.markdown(f"### 🛡️ 완료된 퀘스트 #{q['quest_id']}")
                    st.markdown(f"**설명**: {q.get('description') or '설명 없음'}")
                with col_action:
                    st.markdown("<h3 style='color:#2a9d8f; text-align:center; margin-top:10px;'>🏆 수령 완료</h3>", unsafe_allow_html=True)
                    st.caption(f"획득 경험치: +{q.get('reward_xp', 0)} XP")
