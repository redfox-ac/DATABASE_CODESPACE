import streamlit as st

from utils.auth import require_login
from utils.db import fetch_user_inventory

st.set_page_config(page_title="인벤토리 · EcoQuest", layout="wide")
require_login()

user = st.session_state.user_info
inventory = fetch_user_inventory(user["id"])

st.title("🎒 내 인벤토리")
st.caption("모험과 퀘스트를 통해 수집한 테라리움 꾸미기용 아이템 보관함입니다.")

# 아이템 메타데이터 정의 (아이콘 및 상세 설명)
ITEM_INFO = {
    "밝은 하늘": {"icon": "☀️", "desc": "맑고 파란 하늘로, 테라리움에 따스한 햇살과 에너지를 제공합니다. 광합성을 촉진하는 기초가 됩니다."},
    "노을빛 하늘": {"icon": "🌅", "desc": "아름다운 붉은 저녁 노을로, 대기 중에 따스한 온기를 감돌게 하며 평온한 분위기를 조성합니다."},
    "별이 빛나는 밤하늘": {"icon": "🌌", "desc": "무수한 별들이 가득 찬 밤하늘로, 밤에 활동하는 생물들에게 안정감을 주는 신비로운 배경입니다."},
    "푸른 잔디": {"icon": "🌱", "desc": "초록빛 싱그러운 잔디로, 토양 유실을 방지하고 곤충과 초식동물들이 살아가는 풍요로운 터전이 됩니다."},
    "작은 선인장": {"icon": "🌵", "desc": "건조한 기후에도 적응이 뛰어난 식물입니다. 최소한의 수분으로 생명력을 증명하며 생태 다변화에 기여합니다."},
    "단풍나무": {"icon": "🍁", "desc": "붉게 물든 낙엽성 교목입니다. 계절에 따른 유기물 공급과 조류의 서식처 역할을 훌륭히 수행합니다."},
    "귀여운 토끼": {"icon": "🐇", "desc": "깡충깡충 뛰어다니는 온순한 초식동물입니다. 풀을 먹어 식물 생장을 자극하고 생태계의 허리 역할을 합니다."},
    "노래하는 새": {"icon": "🐦", "desc": "아름다운 울음소리로 생태계에 활력을 불어넣는 조류입니다. 해충을 잡아먹고 식물의 씨앗을 멀리 퍼뜨려 줍니다."},
    "아기 사슴": {"icon": "🦌", "desc": "선한 눈망울을 지닌 중형 초식동물입니다. 깊은 숲 생태계의 균형과 평화를 상징하며 온순하게 서식합니다."}
}

def get_item_meta(item_name: str) -> dict:
    return ITEM_INFO.get(item_name, {"icon": "📦", "desc": "에코퀘스트 탐험을 통해 획득한 신비로운 생태계 아이템입니다."})

if not inventory:
    st.info("보유 중인 아이템이 없습니다. 퀘스트를 완료하거나 생물을 수집해 보세요!")
else:
    # 세션 상태에 선택된 아이템 초기화
    if "selected_item_id" not in st.session_state or not any(item["item_id"] == st.session_state.selected_item_id for item in inventory):
        st.session_state.selected_item_id = inventory[0]["item_id"]

    # 선택된 아이템 객체 찾기
    selected_item = next((item for item in inventory if item["item_id"] == st.session_state.selected_item_id), inventory[0])
    selected_meta = get_item_meta(selected_item["item_name"])

    left_col, right_col = st.columns([3, 2], gap="large")

    with left_col:
        # 카테고리별 분류 탭 생성
        tab_names = ["전체", "🌿 식물", "🐾 동물", "🌌 배경"]
        tabs = st.tabs(tab_names)

        # 각 탭에 따른 필터링 리스트 빌드
        for tab_idx, tab in enumerate(tabs):
            with tab:
                if tab_idx == 0:
                    filtered = inventory
                elif tab_idx == 1:
                    filtered = [item for item in inventory if item.get("category_name") == "식물"]
                elif tab_idx == 2:
                    filtered = [item for item in inventory if item.get("category_name") == "동물"]
                elif tab_idx == 3:
                    filtered = [item for item in inventory if item.get("category_name") == "배경"]

                if not filtered:
                    st.caption("해당 카테고리에 보유한 아이템이 없습니다.")
                    continue

                # 동적 CSS 룰 생성 (각 아이템의 등급/테두리 스타일링 적용)
                css_rules = []
                for item in filtered:
                    item_id = item["item_id"]
                    qty = item["quantity"]
                    meta = get_item_meta(item["item_name"])
                    
                    # 카테고리에 따른 동적 테두리 색상 지정
                    cat_name = item.get("category_name")
                    if cat_name == "식물":
                        border_color = "#2ecc71"
                        box_shadow = "0 0 10px rgba(46, 204, 113, 0.1), inset 0 0 8px rgba(255, 255, 255, 0.05)"
                        tag_bg = "#2ecc71"
                    elif cat_name == "동물":
                        border_color = "#3498db"
                        box_shadow = "0 0 10px rgba(52, 152, 219, 0.1), inset 0 0 8px rgba(255, 255, 255, 0.05)"
                        tag_bg = "#3498db"
                    else: # 배경 또는 기타
                        border_color = "#9b59b6"
                        box_shadow = "0 0 10px rgba(155, 89, 182, 0.1), inset 0 0 8px rgba(255, 255, 255, 0.05)"
                        tag_bg = "#9b59b6"

                    # 선택된 경우 더욱 강하게 하이라이트
                    if item_id == st.session_state.selected_item_id:
                        border_style = "solid"
                        border_width = "2px"
                        box_shadow = f"0 0 16px {border_color}, inset 0 0 12px rgba(255, 255, 255, 0.1)"
                    else:
                        border_style = "solid"
                        border_width = "1px"

                    css_rules.append(f"""
                    .st-key-inv_btn_{tab_idx}_{item_id} button {{
                        border: {border_width} {border_style} {border_color} !important;
                        box-shadow: {box_shadow} !important;
                    }}
                    .st-key-inv_btn_{tab_idx}_{item_id} button:hover {{
                        border: 2px solid {border_color} !important;
                        box-shadow: 0 6px 15px {border_color} !important;
                    }}
                    .st-key-inv_btn_{tab_idx}_{item_id} button::after {{
                        content: "×{qty}" !important;
                        position: absolute !important;
                        top: -8px !important;
                        left: 50% !important;
                        transform: translateX(-50%) !important;
                        font-size: 0.65rem !important;
                        font-weight: bold !important;
                        background: {tag_bg} !important;
                        color: white !important;
                        padding: 1px 6px !important;
                        border-radius: 6px !important;
                        border: 1px solid rgba(255, 255, 255, 0.15) !important;
                        white-space: nowrap !important;
                        line-height: 1.2 !important;
                        pointer-events: none !important;
                    }}
                    """)

                # 스타일시트 렌더링
                styles = f"""
                <style>
                .st-key-inventory-grid-{tab_idx} div[data-testid="stHorizontalBlock"] {{
                    display: flex !important;
                    flex-wrap: wrap !important;
                    gap: 20px 16px !important;
                    justify-content: flex-start !important;
                    width: 100% !important;
                }}
                .st-key-inventory-grid-{tab_idx} div[data-testid="stColumn"] {{
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
                .st-key-inventory-grid-{tab_idx} div[data-testid="stButton"] {{
                    width: 68px !important;
                    height: 68px !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }}
                .st-key-inventory-grid-{tab_idx} div[data-testid="stButton"] button {{
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
                .st-key-inventory-grid-{tab_idx} .inventory-item-label {{
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
                st.markdown(styles, unsafe_allow_html=True)

                # 아이템 그리드 렌더링
                with st.container(key=f"inventory-grid-{tab_idx}"):
                    cols = st.columns(len(filtered))
                    for col, item in zip(cols, filtered):
                        item_id = item["item_id"]
                        meta = get_item_meta(item["item_name"])
                        
                        # 선택되었을 때 카테고리에 맞는 명시적 색상 적용
                        if item_id == st.session_state.selected_item_id:
                            cat_name = item.get("category_name")
                            if cat_name == "식물":
                                label_color = "#2ecc71"
                            elif cat_name == "동물":
                                label_color = "#3498db"
                            else:
                                label_color = "#9b59b6"
                        else:
                            label_color = "var(--text-color)"
                        
                        with col:
                            if st.button(meta["icon"], key=f"inv_btn_{tab_idx}_{item_id}"):
                                st.session_state.selected_item_id = item_id
                                st.rerun()
                            st.markdown(
                                f"<span class='inventory-item-label' style='color: {label_color};' title='{item['item_name']}'>{item['item_name']}</span>",
                                unsafe_allow_html=True
                            )

    with right_col:
        # 아이템 상세 정보를 카드 형태로 표시
        st.subheader("🔍 아이템 상세 정보")
        
        # 글래스모피즘 상세 카드 구현
        cat_name = selected_item.get("category_name")
        if cat_name == "식물":
            tint_border = "rgba(46, 204, 113, 0.4)"
            cat_color = "#2ecc71"
        elif cat_name == "동물":
            tint_border = "rgba(52, 152, 219, 0.4)"
            cat_color = "#3498db"
        else:
            tint_border = "rgba(155, 89, 182, 0.4)"
            cat_color = "#9b59b6"

        st.markdown(
            f"""<div style="
background: linear-gradient(135deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.01));
backdrop-filter: blur(10px);
-webkit-backdrop-filter: blur(10px);
border: 1px solid {tint_border};
border-radius: 16px;
padding: 30px;
box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
color: var(--text-color);
display: flex;
flex-direction: column;
align-items: center;
text-align: center;
">
<div style="font-size: 5rem; margin-bottom: 15px; filter: drop-shadow(0 0 15px rgba(255, 255, 255, 0.1));">{selected_meta['icon']}</div>
<h2 style="margin: 0 0 8px 0; font-family: 'Outfit', sans-serif; font-weight: bold; color: var(--text-color);">{selected_item['item_name']}</h2>
<div style="
background-color: rgba(255, 255, 255, 0.08);
color: {cat_color};
font-weight: bold;
font-size: 0.8rem;
padding: 4px 12px;
border-radius: 20px;
margin-bottom: 20px;
border: 1px solid {tint_border};
">{cat_name} 카테고리</div>
<div style="width: 100%; text-align: left; background: rgba(0, 0, 0, 0.15); padding: 15px 20px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 20px;">
<span style="font-size: 0.85rem; opacity: 0.6; display: block; margin-bottom: 4px;">보유 현황</span>
<span style="font-size: 1.5rem; font-weight: bold; color: var(--text-color);">📦 {selected_item['quantity']} 개 보유 중</span>
</div>
<div style="width: 100%; text-align: left; background: rgba(255, 255, 255, 0.02); padding: 20px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.03); min-height: 120px;">
<span style="font-size: 0.85rem; opacity: 0.6; display: block; margin-bottom: 8px;">생태 환경 정보</span>
<p style="margin: 0; font-size: 0.95rem; line-height: 1.6; color: var(--text-color); word-break: keep-all;">{selected_meta['desc']}</p>
</div>
<div style="margin-top: 30px; font-size: 0.8rem; opacity: 0.5; color: var(--text-color);">
💡 이 아이템은 <b>홈(메인 화면)</b>의 테라리움 그리드에서 직접 클릭하여 장착 및 꾸미기가 가능합니다.
</div>
</div>""",
            unsafe_allow_html=True
        )
