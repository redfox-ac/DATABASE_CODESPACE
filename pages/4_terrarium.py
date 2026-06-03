import streamlit as st

from utils.auth import require_login
from utils.db import (
    equip_terrarium_item,
    fetch_terrarium_layout,
    fetch_user_inventory,
    unequip_terrarium_item,
)

st.set_page_config(page_title="테라리움 · EcoQuest", layout="wide")
require_login()

user = st.session_state.user_info
layout = fetch_terrarium_layout(user["id"])
inventory = fetch_user_inventory(user["id"])

st.title("🪴 테라리움")

def _slot_by_id(slot_id: int) -> dict | None:
    return next((s for s in layout if s["slot_id"] == slot_id), None)


def _items_for_slot(slot: dict) -> list[dict]:
    cat_id = slot.get("slot_category_id")
    if cat_id is None:
        return inventory
    return [item for item in inventory if item.get("category_id") == cat_id]


@st.dialog("슬롯 꾸미기")
def slot_editor(slot_id: int):
    slot = _slot_by_id(slot_id)
    if not slot:
        st.error("슬롯 정보를 찾을 수 없습니다.")
        return

    st.markdown(f"### {slot['slot_name']}")
    if slot.get("slot_description"):
        st.caption(slot["slot_description"])
    cat_label = slot.get("slot_category_name") or "제한 없음"
    st.markdown(f"**장착 가능 카테고리:** {cat_label}")

    equipped_id = slot.get("equipped_item_id")
    equipped_name = slot.get("equipped_item_name")

    if equipped_id:
        st.success(f"현재 장착: **{equipped_name}**")
        if st.button("장착 해제", type="secondary", key=f"unequip_{slot_id}"):
            err = unequip_terrarium_item(user["id"], slot_id)
            if err:
                st.error(err)
            else:
                st.rerun()
    else:
        st.info("비어 있는 슬롯입니다.")

    eligible = _items_for_slot(slot)
    st.divider()
    st.markdown("**인벤토리에서 선택**")

    if not eligible:
        st.caption(
            f"'{cat_label}' 카테고리 아이템이 인벤토리에 없습니다. "
            "퀘스트 보상 등으로 아이템을 모은 뒤 다시 시도해 보세요."
        )
        return

    options = {
        f"{item['item_name']} (보유 {item['quantity']})": item["item_id"]
        for item in eligible
    }
    choice = st.selectbox("아이템", list(options.keys()), key=f"pick_{slot_id}")
    if st.button("이 아이템 장착", type="primary", key=f"equip_{slot_id}"):
        item_id = options[choice]
        err = equip_terrarium_item(user["id"], slot_id, item_id)
        if err:
            st.error(err)
        else:
            st.rerun()


left, right = st.columns([1, 2])

with left:
    st.subheader("환경 설정")
    st.markdown(
        """
        나만의 가상 생태계를 꾸며 보세요.

        - 슬롯마다 허용된 카테고리의 아이템만 장착할 수 있습니다.
        - 슬롯을 선택한 뒤 **꾸미기**로 장착·해제할 수 있습니다.
        """
    )

    if not layout:
        st.info("등록된 테라리움 슬롯이 없습니다.")
    else:
        slot_labels = {
            s["slot_id"]: f"{s['slot_name']} ({s.get('slot_category_name') or '전체'})"
            for s in layout
        }
        selected_id = st.selectbox(
            "슬롯 선택",
            options=list(slot_labels.keys()),
            format_func=lambda sid: slot_labels[sid],
            key="terrarium_slot_picker",
        )
        selected = _slot_by_id(selected_id)
        if selected and selected.get("slot_description"):
            st.markdown(selected["slot_description"])
        if st.button("선택한 슬롯 꾸미기", type="primary", use_container_width=True):
            slot_editor(selected_id)

    st.divider()
    st.markdown("**내 인벤토리**")
    if not inventory:
        st.caption("보유 아이템이 없습니다.")
    else:
        for item in inventory:
            qty = item.get("quantity", 1)
            cat = item.get("category_name") or "미분류"
            st.markdown(f"- {item['item_name']} · {cat} ×{qty}")

with right:
    st.subheader("슬롯 배치")
    if not layout:
        st.info("테라리움 슬롯 정의가 아직 없습니다.")
    else:
        grid_cols = 3
        for i in range(0, len(layout), grid_cols):
            cols = st.columns(grid_cols)
            for col, slot in zip(cols, layout[i : i + grid_cols]):
                with col:
                    with st.container(border=True):
                        st.markdown(f"#### {slot['slot_name']}")
                        cat = slot.get("slot_category_name")
                        if cat:
                            st.caption(f"카테고리: {cat}")
                        equipped_name = slot.get("equipped_item_name")
                        if equipped_name:
                            st.success(f"장착: {equipped_name}")
                        else:
                            st.caption("비어 있음")
                        if st.button(
                            "꾸미기",
                            key=f"edit_slot_{slot['slot_id']}",
                            use_container_width=True,
                        ):
                            slot_editor(slot["slot_id"])
