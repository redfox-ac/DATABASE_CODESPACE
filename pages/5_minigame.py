import random
import time

import streamlit as st

from utils.auth import require_login
from utils.db import (
    fetch_all_dictionary,
    fetch_random_picture_for_minigame,
    record_picture_trust,
    check_picture_valid_for_minigame,
    check_user_daily_minigame_participation,
)

PLACEHOLDER_IMAGE = "https://dummyimage.com/600x400/40916c/ffffff&text=EcoQuest+CAPTCHA"

st.set_page_config(page_title="미니게임 · EcoQuest", layout="wide")
require_login()

st.title("🎮 데이터 신뢰성 검증")
st.caption("다른 탐험가가 올린 사진의 생물 종을 맞춰 주세요.")

dictionary = fetch_all_dictionary()
if len(dictionary) < 4:
    st.info("미니게임을 진행하려면 도감에 최소 4종의 생물 데이터가 필요합니다.")
    st.stop()

user = st.session_state.user_info

# Check today's participation
if check_user_daily_minigame_participation(user["id"]):
    if "minigame_feedback" in st.session_state:
        status, msg = st.session_state.minigame_feedback
        if status == "success":
            st.success(msg)
        else:
            st.error(msg)
        del st.session_state.minigame_feedback
    st.info("오늘의 참여가 완료되었습니다.")
    st.stop()

# Verify cached picture validity on load (in case user uploaded/answered it in another page/session)
if st.session_state.get("captcha_picture_id") is not None:
    if not check_picture_valid_for_minigame(user["id"], st.session_state.captcha_picture_id):
        st.session_state.captcha_correct_id = None
        st.session_state.captcha_choices = []
        st.session_state.captcha_image = PLACEHOLDER_IMAGE
        st.session_state.captcha_picture_id = None
        st.session_state.captcha_start_time = None

if "captcha_correct_id" not in st.session_state:
    st.session_state.captcha_correct_id = None
    st.session_state.captcha_choices = []
    st.session_state.captcha_image = PLACEHOLDER_IMAGE
    st.session_state.captcha_picture_id = None
    st.session_state.captcha_start_time = None

if st.button("새 문제 받기") or not st.session_state.captcha_choices:
    pic = fetch_random_picture_for_minigame(user["id"])
    if not pic:
        st.warning("현재 검증할 수 있는 탐험가의 사진 데이터가 준비되지 않았습니다. 잠시 후 다시 시도해 주세요.")
        st.stop()

    primary_id = pic["candidate_dictionary_id"]
    primary_name = pic["primary_name"]

    # AI가 판별한 후보종들을 기본 선택지로 사용
    candidates = [{"id": c["id"], "name": c["name"]} for c in pic["candidates"]]

    # 1순위 대표 후보(정답)가 후보 목록에 포함되어 있는지 확인 및 추가
    if not any(c["id"] == primary_id for c in candidates):
        candidates.append({"id": primary_id, "name": primary_name})

    # 중복 제거된 후보 ID 셋
    candidate_ids = {c["id"] for c in candidates}

    # 4개 미만인 경우 도감에서 랜덤하게 다른 종을 선택지로 채움 (중복 방지)
    if len(candidates) < 4:
        others = [d for d in dictionary if d["id"] not in candidate_ids]
        needed = 4 - len(candidates)
        wrong = random.sample(others, min(needed, len(others)))
        choices = candidates + wrong
    else:
        # 4개 이상이면 상위 4개만 사용
        choices = candidates[:4]

    random.shuffle(choices)

    st.session_state.captcha_correct_id = primary_id
    st.session_state.captcha_choices = choices
    st.session_state.captcha_image = pic["storage_url"]
    st.session_state.captcha_picture_id = pic["id"]
    st.session_state.captcha_start_time = time.time()

_, img_col, _ = st.columns([1, 2, 1])
with img_col:
    st.image(st.session_state.captcha_image, use_container_width=True)

st.markdown("#### 이 사진의 생물은 무엇일까요?")

row1_col1, row1_col2 = st.columns(2)
row2_col1, row2_col2 = st.columns(2)
button_cols = [row1_col1, row1_col2, row2_col1, row2_col2]

for col, choice in zip(button_cols, st.session_state.captcha_choices):
    with col:
        if st.button(choice["name"], key=f"captcha_{choice['id']}", use_container_width=True):
            # Calculate response time (ms)
            if st.session_state.captcha_start_time is not None:
                response_time = int((time.time() - st.session_state.captcha_start_time) * 1000)
            else:
                response_time = 0
            
            # Record response to database
            record_picture_trust(
                user_id=user["id"],
                picture_id=st.session_state.captcha_picture_id,
                selected_candidate_id=choice["id"],
                response_time=response_time,
            )
            
            st.session_state.minigame_feedback = (
                "success",
                "답변이 등록되었습니다. 추후 답변이 정답으로 판정될 시 보상이 지급됩니다."
            )
            st.session_state.captcha_choices = []
            st.rerun()

st.markdown("---")
if st.button("해당 문제의 답이 없나요?", type="secondary"):
    st.info("신고가 접수되었습니다. 다른 문제로 넘어가 주세요.")
    st.session_state.captcha_choices = []
    st.rerun()
