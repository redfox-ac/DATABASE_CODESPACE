import streamlit as st

from utils.auth import init_session, render_sidebar_nav
from utils.db import (
    authenticate_user,
    fetch_user,
    fetch_terrarium_layout,
    fetch_user_inventory,
    equip_terrarium_item,
    unequip_terrarium_item,
)
from utils.terrarium_renderer import render_terrarium_svg

st.set_page_config(page_title="EcoQuest", layout="wide")
init_session()

# ==========================================
# 대시보드 화면 구성
# ==========================================

if st.session_state.logged_in and st.session_state.user_info:
    render_sidebar_nav()

    user = st.session_state.user_info
    
    # 세션 갱신
    fresh = fetch_user(user["id"], nickname=user.get("nickname", ""))
    if fresh:
        st.session_state.user_info = fresh
        user = fresh

    layout = fetch_terrarium_layout(user["id"])
    inventory = fetch_user_inventory(user["id"])

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

    # 하단 영역: 테라리움 그래픽 (메인 컨텐츠)
    if not layout:
        st.info("등록된 테라리움 슬롯 정의가 없습니다.")
    else:
        # 동적 저폴리곤(Low-Poly) SVG 그래픽 코드 생성
        import re
        raw_svg = render_terrarium_svg(layout)
        svg_code = re.sub(r'\s+', ' ', raw_svg)
        
        # 각 슬롯별 스타일 규칙 동적 빌드
        css_rules = []
        for slot in layout:
            slot_id = slot["slot_id"]
            equipped = slot.get("equipped_item_name")
            
            if equipped:
                border_style = "solid"
                slot_name = slot.get("slot_name")
                if slot_name == "식물":
                    border_color = "#2ecc71"
                    box_shadow = "0 0 12px rgba(46, 204, 113, 0.15), inset 0 0 8px rgba(255, 255, 255, 0.05)"
                    hover_shadow = "0 6px 20px rgba(46, 204, 113, 0.25)"
                    tag_bg = "#2ecc71"
                elif slot_name == "동물":
                    border_color = "#3498db"
                    box_shadow = "0 0 12px rgba(52, 152, 219, 0.15), inset 0 0 8px rgba(255, 255, 255, 0.05)"
                    hover_shadow = "0 6px 20px rgba(52, 152, 219, 0.25)"
                    tag_bg = "#3498db"
                else:  # 배경
                    border_color = "#9b59b6"
                    box_shadow = "0 0 12px rgba(155, 89, 182, 0.15), inset 0 0 8px rgba(255, 255, 255, 0.05)"
                    hover_shadow = "0 6px 20px rgba(155, 89, 182, 0.25)"
                    tag_bg = "#9b59b6"
                tag_color = "white"
            else:
                border_style = "dashed"
                border_color = "rgba(255, 255, 255, 0.12)"
                box_shadow = "inset 0 0 8px rgba(0, 0, 0, 0.5)"
                hover_shadow = "0 6px 15px rgba(255, 255, 255, 0.08)"
                tag_bg = "rgba(255, 255, 255, 0.15)"
                tag_color = "rgba(255, 255, 255, 0.3)"
                
            css_rules.append(f"""
            .st-key-slot_btn_{slot_id} button {{
                border: 1px {border_style} {border_color} !important;
                box-shadow: {box_shadow} !important;
            }}
            .st-key-slot_btn_{slot_id} button:hover {{
                border: 1px {border_style} {border_color} !important;
                box-shadow: {hover_shadow} !important;
            }}
            .st-key-slot_btn_{slot_id} button::after {{
                content: "{slot['slot_name']}" !important;
                position: absolute !important;
                top: -8px !important;
                left: 50% !important;
                transform: translateX(-50%) !important;
                font-size: 0.65rem !important;
                font-weight: bold !important;
                background: {tag_bg} !important;
                color: {tag_color} !important;
                padding: 1px 6px !important;
                border-radius: 6px !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                white-space: nowrap !important;
                line-height: 1.2 !important;
                pointer-events: none !important;
            }}
            """)

        left_col, right_col = st.columns([2.0, 1.0], gap="large")
        
        with left_col:
            # 입체 유리 돔 테라리움 카드 렌더링 (가로 배치 레이아웃 - PC화면(>=641px)에서는 위아래로 꽉 채우고, 모바일(<=640px)에서는 420px 유지)
            html_card = f"""
            <style>
            .terrarium-card-resizable {{
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.01));
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                padding: 32px;
                box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.2);
                display: flex;
                flex-direction: row;
                justify-content: center;
                align-items: center;
                width: 100%;
                height: 420px;
                margin: 10px 0 30px 0;
                box-sizing: border-box;
            }}
            @media (min-width: 640px) {{
                .terrarium-card-resizable {{
                    height: calc(100vh - 160px);
                    min-height: 420px;
                }}
            }}
            </style>
            <div class="terrarium-card-resizable">
                <div style="width: 100%; height: 100%; display: flex; justify-content: center; align-items: center;">
                    {svg_code}
                </div>
            </div>
            """
            st.markdown(re.sub(r'\s+', ' ', html_card), unsafe_allow_html=True)
            
        with right_col:
            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            
            # CSS Stylesheet
            css_styles = f"""
            <style>
            .st-key-equipment-grid div[data-testid="stHorizontalBlock"] {{
                display: flex !important;
                flex-wrap: wrap !important;
                gap: 16px 12px !important;
                justify-content: center !important;
                width: 100% !important;
            }}
            .st-key-equipment-grid div[data-testid="stColumn"] {{
                width: 68px !important;
                min-width: 68px !important;
                max-width: 68px !important;
                flex-basis: 68px !important;
                flex-shrink: 0 !important;
                display: flex !important;
                flex-direction: column !important;
                align-items: center !important;
                gap: 8px !important;
            }}
            .st-key-equipment-grid div[data-testid="stButton"] {{
                width: 68px !important;
                height: 68px !important;
                margin: 0 !important;
                padding: 0 !important;
            }}
            .st-key-equipment-grid div[data-testid="stButton"] button {{
                width: 68px !important;
                height: 68px !important;
                border-radius: 12px !important;
                background: rgba(255, 255, 255, 0.03) !important;
                display: flex !important;
                justify-content: center !important;
                align-items: center !important;
                font-size: 1.8rem !important;
                padding: 0 !important;
                position: relative !important;
                overflow: visible !important;
                margin: 0 !important;
                color: var(--text-color) !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            }}
            .st-key-equipment-grid .terrarium-slot-label {{
                font-size: 0.75rem;
                font-weight: 500;
                text-align: center;
                width: 100%;
                white-space: nowrap;
                text-overflow: ellipsis;
                overflow: hidden;
                transition: color 0.3s ease;
                display: block;
                margin-top: 4px;
            }}
            {"".join(css_rules)}
            </style>
            """
            st.markdown(css_styles, unsafe_allow_html=True)
            
            st.markdown("<div style='font-size: 0.8rem; opacity: 0.5; font-weight: bold; color: var(--text-color); margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.5px;'>테라리움 꾸미기</div>", unsafe_allow_html=True)
            
            with st.container(key="equipment-grid"):
                cols = st.columns(len(layout))
                for col, slot in zip(cols, layout):
                    slot_name = slot['slot_name']
                    equipped = slot.get('equipped_item_name')
                    
                    # 아이콘 설정
                    icon = "🌌"
                    if slot_name == "식물":
                        icon = "🌿"
                    elif slot_name == "동물":
                        icon = "🐾"
                        
                    label = equipped if equipped else "비어 있음"
                    if equipped:
                        if slot_name == "식물":
                            label_color = "#2ecc71"
                        elif slot_name == "동물":
                            label_color = "#3498db"
                        else:
                            label_color = "#9b59b6"
                    else:
                        label_color = "rgba(255, 255, 255, 0.3)"
                    
                    with col:
                        if st.button(icon, key=f"slot_btn_{slot['slot_id']}"):
                            slot_editor(slot["slot_id"])
                        st.markdown(f"<span class='terrarium-slot-label' style='color: {label_color};' title='{label}'>{label}</span>", unsafe_allow_html=True)
            
            st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)

else:
    st.title("🌿 EcoQuest")
    st.caption("닉네임으로 로그인하고 생태 탐험을 시작하세요.")

    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.markdown(
            """
            <div style="
                border: 1px solid var(--primary-color);
                border-radius: 12px;
                padding: 2rem 1.5rem;
                background: var(--secondary-background-color);
                box-shadow: 0 4px 24px rgba(0,0,0,0.1);
            ">
            <h3 style="text-align:center; margin-top:0; color:var(--text-color);">🔐 탐험가 로그인</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("login_form", clear_on_submit=False):
            nickname = st.text_input("닉네임", placeholder="예: eco_explorer")
            submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)
            if submitted:
                if not nickname.strip():
                     st.warning("닉네임을 입력해 주세요.")
                else:
                     user = authenticate_user(nickname)
                     if user:
                         st.session_state.logged_in = True
                         st.session_state.user_info = user
                         st.rerun()

        st.markdown("<div style='text-align: center; margin-top: 15px;'></div>", unsafe_allow_html=True)
        st.page_link("pages/6_admin.py", label="🔬 연구자인가요? 다음 페이지에서 생물 데이터 신청하기", use_container_width=True)
