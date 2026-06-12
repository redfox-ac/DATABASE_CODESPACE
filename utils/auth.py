import streamlit as st


def init_session() -> None:
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user_info" not in st.session_state:
        st.session_state.user_info = None


def render_sidebar_nav() -> None:
    """로그인 상태에서 모든 페이지에 동일한 좌측 메뉴를 표시합니다."""
    user = st.session_state.user_info
    with st.sidebar:
        st.markdown("### 🌿 EcoQuest")
        st.caption(f"환영합니다, **{user['nickname']}**님!")
        st.divider()
        st.page_link("pages/1_home.py", label="홈", icon="🏠")
        st.page_link("pages/2_dictionary.py", label="도감", icon="📖")
        st.page_link("pages/3_quest.py", label="퀘스트", icon="🎯")
        st.page_link("pages/4_terrarium.py", label="테라리움", icon="🪴")
        st.divider()
        if st.button("로그아웃", width="stretch"):
            st.session_state.logged_in = False
            st.session_state.user_info = None
            st.switch_page("app.py")


def require_login() -> None:
    """미로그인 차단 + 로그인 시 사이드바 메뉴 유지."""
    init_session()
    if not st.session_state.get("logged_in") or not st.session_state.get("user_info"):
        st.warning("로그인이 필요합니다. 메인 화면에서 닉네임으로 로그인해 주세요.")
        st.page_link("app.py", label="로그인하러 가기", icon="🔐")
        st.stop()
    render_sidebar_nav()
