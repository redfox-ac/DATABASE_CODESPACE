import streamlit as st
from utils.auth import require_login
from utils.db import (
    fetch_available_quests,
    accept_quest,
    fetch_user_quests,
    claim_quest_reward,
    fetch_user,
    cleanup_expired_quests,
    check_user_daily_minigame_participation,
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
    
    has_participated_today = check_user_daily_minigame_participation(user_id)
    
    # 가상 미니게임 일일 퀘스트 주입 (UI 전용 - 미참여 시에만 진행 중 탭에 노출)
    quests_to_render = []
    if not has_participated_today:
        minigame_quest = {
            "quest_id": "일일",
            "status": "in_progress",
            "description": "매일 한 번씩 다른 탐험가가 등록한 사진을 보고 생물종을 판별하여 데이터 신뢰성 검증에 참여하고 보상을 받아보세요.",
            "reward_xp": 10,
            "rewards": [],
            "is_minigame": True
        }
        quests_to_render.append(minigame_quest)
        
    quests_to_render += active_quests
    
    for q in quests_to_render:
        is_minigame = q.get("is_minigame", False)
        is_completed = q["status"] == "completed"
        
        with st.container(border=True):
            col_text, col_action = st.columns([3, 1])
            
            with col_text:
                title_icon = "✨" if is_completed else "🏃"
                status_tag = (
                    '<span style="background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; padding: 2px 8px; border-radius: 4px; font-size: 13px; font-weight: bold; vertical-align: middle; margin-left: 8px;">달성 완료</span>'
                    if is_completed else
                    '<span style="background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; padding: 2px 8px; border-radius: 4px; font-size: 13px; font-weight: bold; vertical-align: middle; margin-left: 8px;">진행 중</span>'
                )
                if is_minigame:
                    st.markdown(f"### {title_icon} 미니게임 참여 {status_tag}", unsafe_allow_html=True)
                else:
                    st.markdown(f"### {title_icon} 퀘스트 #{q['quest_id']} {status_tag}", unsafe_allow_html=True)
                
                st.markdown(f"**설명**: {q.get('description') or '설명 없음'}")
                st.markdown("**목표 달성도:**")
                if is_minigame:
                    current = 1 if has_participated_today else 0
                    st.write(f"- 🎮 **생물종 검증** 참여: {current} / 1")
                    st.progress(1.0 if has_participated_today else 0.0)
                else:
                    for target in q.get("target_species", []):
                        current = target["current_count"]
                        limit = target["target_count"]
                        pct = min(current / limit, 1.0) if limit > 0 else 0.0
                        st.write(f"- 🌿 **{target['species_name']}** 발견: {current} / {limit}")
                        st.progress(pct)
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
                
                if is_minigame:
                    if is_completed:
                        st.button("수행 완료", key="claim_minigame", disabled=True, use_container_width=True)
                    else:
                        if st.button("🎮 미니게임 시작하기", key="start_minigame", type="primary", use_container_width=True):
                            st.session_state.captcha_correct_id = None
                            st.session_state.captcha_choices = []
                            st.session_state.captcha_image = "https://dummyimage.com/600x400/40916c/ffffff&text=EcoQuest+CAPTCHA"
                            st.session_state.captcha_picture_id = None
                            st.session_state.captcha_start_time = None
                            st.switch_page("pages/5_minigame.py")
                elif is_completed:
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
                    status_tag = '<span style="background-color: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; padding: 2px 8px; border-radius: 4px; font-size: 13px; font-weight: bold; vertical-align: middle; margin-left: 8px;">수락 가능</span>'
                    st.markdown(f"### 🗺️ 퀘스트 #{q['id']} {status_tag}", unsafe_allow_html=True)
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
                    if st.button("🎯 퀘스트 수락", key=f"accept_{q['id']}", type="primary", use_container_width=True):
                        if accept_quest(user_id, q["id"]):
                            st.toast(f"🎯 퀘스트 #{q['id']}를 수락했습니다! 진행 중인 퀘스트 탭에서 확인하세요.")
                            st.rerun()

# 3. 완료된 퀘스트
with tab_claimed:
    all_user_quests = fetch_user_quests(user_id)
    claimed_quests = [q for q in all_user_quests if q["status"] == "claimed"]
    
    # 오늘 미니게임을 완료했다면 완료 목록에 노출
    if has_participated_today:
        minigame_claimed = {
            "quest_id": "일일",
            "description": "매일 한 번씩 다른 탐험가가 등록한 사진을 보고 생물종을 판별하여 데이터 신뢰성 검증에 참여하고 보상을 받아보세요.",
            "reward_xp": 10,
            "rewards": [],
            "is_minigame": True
        }
        claimed_quests = [minigame_claimed] + claimed_quests
        
    if not claimed_quests:
        st.info("수령을 완료한 퀘스트가 아직 없습니다.")
    else:
        for q in claimed_quests:
            is_minigame = q.get("is_minigame", False) or q["quest_id"] == "일일"
            with st.container(border=True):
                col_text, col_action = st.columns([3, 1])
                with col_text:
                    status_tag = '<span style="background-color: #e2e3e5; color: #383d41; border: 1px solid #d6d8db; padding: 2px 8px; border-radius: 4px; font-size: 13px; font-weight: bold; vertical-align: middle; margin-left: 8px;">수령 완료</span>'
                    if is_minigame:
                        st.markdown(f"### ✅ 미니게임 참여 {status_tag}", unsafe_allow_html=True)
                    else:
                        st.markdown(f"### ✅ 퀘스트 #{q['quest_id']} {status_tag}", unsafe_allow_html=True)
                    st.markdown(f"**설명**: {q.get('description') or '설명 없음'}")
                with col_action:
                    st.markdown("<h3 style='color:#2a9d8f; text-align:center; margin-top:10px;'>🏆 수령 완료</h3>", unsafe_allow_html=True)
                    st.caption(f"획득 경험치: +{q.get('reward_xp', 0)} XP")
                        

