import streamlit as st

from utils.auth import require_login
from utils.db import fetch_terrarium_slots

st.set_page_config(page_title="테라리움 · EcoQuest", layout="wide")
require_login()

user = st.session_state.user_info
slots = fetch_terrarium_slots(user["id"])

st.title("🪴 테라리움")

left, right = st.columns([1, 2])

with left:
    st.subheader("환경 설정")
    st.markdown(
        """
        나만의 가상 생태계를 꾸며 보세요.

        - 슬롯에 카테고리별 아이템을 장착할 수 있습니다.
        - 장착 변경은 추후 업데이트 예정입니다.
        """
    )
    st.info("왼쪽에서 슬롯을 선택하고, 오른쪽 그리드에서 배치 상태를 확인하세요.")

with right:
    st.subheader("슬롯 배치")
    if not slots:
        st.info("아직 테라리움 슬롯이 없습니다. 탐험을 통해 슬롯을 해제해 보세요!")
    else:
        grid_cols = 3
        for i in range(0, len(slots), grid_cols):
            cols = st.columns(grid_cols)
            for col, slot in zip(cols, slots[i : i + grid_cols]):
                with col:
                    with st.container(border=True):
                        st.markdown(f"#### {slot.get('name', '슬롯')}")
                        equipped = slot.get("equipped_category")
                        if equipped:
                            st.success(f"장착: {equipped}")
                        else:
                            st.caption("비어 있음")
