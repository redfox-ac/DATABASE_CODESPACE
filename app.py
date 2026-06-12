import streamlit as st

from utils.auth import init_session, render_sidebar_nav
from utils.db import authenticate_user

st.set_page_config(page_title="EcoQuest", layout="wide")
init_session()

if st.session_state.logged_in and st.session_state.user_info:
    render_sidebar_nav()

    st.title("🌿 EcoQuest")
    st.markdown(
        """
        사이드바에서 메뉴를 선택해 탐험을 시작하세요.

        - **홈**: 프로필과 생물 수집 렌즈
        - **도감**: 수집한 생물 카드
        - **퀘스트**: 일일·연구 퀘스트 보드
        - **테라리움**: 나만의 생태 환경
        """
    )
else:
    st.title("🌿 EcoQuest")
    st.caption("닉네임으로 로그인하고 생태 탐험을 시작하세요.")

    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.markdown(
            """
            <div style="
                border: 1px solid #2d6a4f;
                border-radius: 12px;
                padding: 2rem 1.5rem;
                background: linear-gradient(145deg, #1b4332 0%, #081c15 100%);
                box-shadow: 0 4px 24px rgba(0,0,0,0.25);
            ">
            <h3 style="text-align:center; margin-top:0; color:#95d5b2;">🔐 탐험가 로그인</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("login_form", clear_on_submit=False):
            nickname = st.text_input("닉네임", placeholder="예: eco_explorer")
            submitted = st.form_submit_button("로그인", type="primary", width="stretch")
            if submitted:
                if not nickname.strip():
                    st.warning("닉네임을 입력해 주세요.")
                else:
                    user = authenticate_user(nickname)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user_info = user
                        st.rerun()
