import random

import streamlit as st

from utils.auth import require_login
from utils.db import fetch_all_dictionary

PLACEHOLDER_IMAGE = "https://dummyimage.com/600x400/40916c/ffffff&text=EcoQuest+CAPTCHA"

st.set_page_config(page_title="미니게임 · EcoQuest", layout="wide")
require_login()

st.title("🎮 데이터 신뢰성 검증")
st.caption("다른 탐험가가 올린 사진의 생물 종을 맞춰 주세요. (캡차 형식 데모)")

dictionary = fetch_all_dictionary()
if len(dictionary) < 4:
    st.info("미니게임을 진행하려면 도감에 최소 4종의 생물 데이터가 필요합니다.")
    st.stop()

if "captcha_correct_id" not in st.session_state:
    st.session_state.captcha_correct_id = None
    st.session_state.captcha_choices = []
    st.session_state.captcha_image = PLACEHOLDER_IMAGE

if st.button("새 문제 받기") or not st.session_state.captcha_choices:
    correct = random.choice(dictionary)
    others = [d for d in dictionary if d["id"] != correct["id"]]
    wrong = random.sample(others, min(3, len(others)))
    choices = [correct] + wrong
    random.shuffle(choices)
    st.session_state.captcha_correct_id = correct["id"]
    st.session_state.captcha_choices = choices
    st.session_state.captcha_image = correct.get("image_url") or PLACEHOLDER_IMAGE

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
            if choice["id"] == st.session_state.captcha_correct_id:
                st.success("정답입니다! 신뢰도 검증에 기여했습니다. (보상 연동 준비 중)")
            else:
                st.error("오답입니다. 다시 시도해 보세요.")
            st.session_state.captcha_choices = []
            st.rerun()

st.markdown("---")
if st.button("해당 문제의 답이 없나요?", type="secondary"):
    st.info("신고가 접수되었습니다. 다른 문제로 넘어가 주세요.")
    st.session_state.captcha_choices = []
    st.rerun()
