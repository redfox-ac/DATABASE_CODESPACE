import streamlit as st
from utils.auth import require_login
from utils.db import (
    fetch_available_quests,
    accept_quest,
    fetch_user_quests,
    claim_quest_reward,
    fetch_user,
)

st.set_page_config(page_title="퀘스트 · EcoQuest", layout="wide")
require_login()

user = st.session_state.user_info
user_id = user["id"]

# Refresh user info to ensure XP and other stats are up to date on page load
fresh_user = fetch_user(user_id, nickname=user.get("nickname", ""))
if fresh_user:
    st.session_state.user_info = fresh_user
    user = fresh_user

st.title("🎯 퀘스트 보드")
st.caption("퀘스트를 수행하여 생태 탐사를 완료하고 특별한 보상을 획득하세요!")

# Tabs for different states
tab_active, tab_available, tab_claimed = st.tabs([
    "🏃 진행 중인 퀘스트",
    "🎁 수락 가능한 퀘스트",
    "✅ 완료된 퀘스트"
])

# 1. 진행 중인 퀘스트
with tab_active:
    all_user_quests = fetch_user_quests(user_id)
    active_quests = [q for q in all_user_quests if q["status"] in ("in_progress", "completed")]
    
    if not active_quests:
        st.info("현재 진행 중인 퀘스트가 없습니다. '수락 가능한 퀘스트' 탭에서 새로운 탐사를 시작해보세요!")
    else:
        for q in active_quests:
            is_completed = q["status"] == "completed"
            
            with st.container(border=True):
                col_text, col_action = st.columns([3, 1])
                
                with col_text:
                    if is_completed:
                        st.markdown(f"### ✨ 퀘스트 #{q['quest_id']} (달성 완료!)")
                    else:
                        st.markdown(f"### 🏃 퀘스트 #{q['quest_id']}")
                    
                    st.markdown(f"**설명**: {q.get('description') or '설명 없음'}")
                    
                    # Target progress
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
                                # Refresh user session
                                updated_user = fetch_user(user_id, nickname=user.get("nickname", ""))
                                if updated_user:
                                    st.session_state.user_info = updated_user
                                st.rerun()
                            else:
                                msg = res.get("message") if res else "오류가 발생했습니다."
                                st.error(f"❌ {msg}")
                    else:
                        st.button("진행 중...", key=f"active_{q['quest_id']}", disabled=True, use_container_width=True)

# 2. 수락 가능한 퀘스트
with tab_available:
    available_quests = fetch_available_quests(user_id)
    
    if not available_quests:
        st.info("현재 수락 가능한 새로운 퀘스트가 없습니다. 나중에 다시 확인해주세요!")
    else:
        for q in available_quests:
            with st.container(border=True):
                col_text, col_action = st.columns([3, 1])
                
                with col_text:
                    st.markdown(f"### 🗺️ 새로운 퀘스트 #{q['id']}")
                    st.markdown(f"**설명**: {q.get('description') or '설명 없음'}")
                    
                    # Target list
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
                    
                    if st.button("🎯 퀘스트 수락", key=f"accept_{q['id']}", type="primary", use_container_width=True):
                        if accept_quest(user_id, q["id"]):
                            st.toast(f"🎯 퀘스트 #{q['id']}를 수락했습니다! 진행 중인 퀘스트 탭에서 확인하세요.")
                            st.rerun()

# 3. 완료된 퀘스트
with tab_claimed:
    all_user_quests = fetch_user_quests(user_id)
    claimed_quests = [q for q in all_user_quests if q["status"] == "claimed"]
    
    if not claimed_quests:
        st.info("수령을 완료한 퀘스트가 아직 없습니다.")
    else:
        for q in claimed_quests:
            with st.container(border=True):
                col_text, col_action = st.columns([3, 1])
                with col_text:
                    st.markdown(f"### 🛡️ 완료된 퀘스트 #{q['quest_id']}")
                    st.markdown(f"**설명**: {q.get('description') or '설명 없음'}")
                with col_action:
                    st.markdown("<h3 style='color:#2a9d8f; text-align:center; margin-top:10px;'>🏆 수령 완료</h3>", unsafe_allow_html=True)
                    st.caption(f"획득 경험치: +{q.get('reward_xp', 0)} XP")
