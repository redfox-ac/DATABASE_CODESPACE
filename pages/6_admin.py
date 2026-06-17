import streamlit as st
import pandas as pd
import io
import datetime

from utils.auth import init_session, render_sidebar_nav
from utils.db import fetch_admin_statistics, fetch_research_data, fetch_all_categories

st.set_page_config(page_title="관리자 대시보드 · EcoQuest", layout="wide")
init_session()

# 로그인 여부에 따라 사이드바 렌더링 방식 조정
if st.session_state.get("logged_in") and st.session_state.get("user_info"):
    render_sidebar_nav()
else:
    with st.sidebar:
        st.markdown("### 🌿 EcoQuest")
        st.page_link("app.py", label="로그인 화면으로 가기", icon="🔐")

st.title("⚙️ 관리자 대시보드")
st.caption("EcoQuest 생태 데이터의 실시간 현황을 모니터링하고 연구 데이터를 추출할 수 있습니다.")

st.divider()

# 1. 요약 통계 지표 (Metrics)
stats = fetch_admin_statistics()
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("전체 가입자 수", f"{stats['total_users']} 명")
with col2:
    st.metric("총 수집 사진 수", f"{stats['total_pictures']} 장")
with col3:
    confirm_rate = (stats['confirmed_pictures'] / max(1, stats['total_pictures'])) * 100
    st.metric("확정 완료 사진", f"{stats['confirmed_pictures']} 장", delta=f"{confirm_rate:.1f}% 확정 완료")
with col4:
    st.metric("검증 진행 중", f"{stats['pending_pictures']} 장")
with col5:
    st.metric("차단된 유저", f"{stats['restricted_users']} 명")

st.divider()

# 2. 연구용 생물 위치 정보 데이터 내보내기 (Data Export)
st.subheader("🔬 연구용 생물 위치 정보 데이터 신청 및 추출")
st.caption("공간 분석(GIS), 생태 연구 등을 위한 좌표가 기재된 관찰 레코드를 필터링하여 CSV 형식으로 내보냅니다.")

# 필터 폼 레이아웃 설정
with st.expander("🔍 데이터 필터링 조건 설정", expanded=True):
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        confirmed_only = st.checkbox("검증 완료(확정)된 관찰 데이터만 추출", value=False)
        protected_only = st.checkbox("법정 보호종 데이터만 추출", value=False)
        
        # 카테고리 목록 조회
        db_categories = fetch_all_categories()
        category_options = ["전체"] + [c["name"] for c in db_categories]
        selected_category = st.selectbox("생물 분류 카테고리 필터", category_options)
        
    with f_col2:
        use_date_filter = st.checkbox("기간 검색 필터 사용", value=False)
        
        # 날짜 범위 설정
        today = datetime.date.today()
        default_start = today - datetime.timedelta(days=30)
        
        start_date = st.date_input("조회 시작일", value=default_start, disabled=not use_date_filter)
        end_date = st.date_input("조회 종료일", value=today, disabled=not use_date_filter)

# 세션 상태 초기화
if "research_data" not in st.session_state:
    st.session_state.research_data = None
if "searched" not in st.session_state:
    st.session_state.searched = False

# 쿼리 및 통계 가공 수행를 위해 인자 조정
category_arg = None if selected_category == "전체" else selected_category
start_arg = start_date if use_date_filter else None
end_arg = end_date if use_date_filter else None

# 명시적 조회 버튼
if st.button("🔍 검색 / 조회", type="primary", use_container_width=True):
    with st.spinner("데이터를 조회하고 통계량을 계산 중..."):
        st.session_state.research_data = fetch_research_data(
            confirmed_only=confirmed_only,
            category=category_arg,
            protected_only=protected_only,
            start_date=start_arg,
            end_date=end_arg
        )
        st.session_state.searched = True

st.markdown("---")

if st.session_state.searched:
    research_data = st.session_state.research_data
    df = pd.DataFrame(research_data)
    
    st.markdown(f"📊 **조회 결과:** 총 **{len(df)}**개의 관찰 레코드가 검색되었습니다.")
    
    if not df.empty:
        # 화면 표시를 위한 컬럼명 한글 변환 매핑
        df_preview = df.copy()
        df_preview.columns = [
            "관찰 ID", "생물종 이름", "분류 카테고리", "보호종 여부",
            "위도", "경도", "확정 여부", "수학적 신뢰도", "이항 p-value",
            "유효 투표수", "관찰 일시"
        ]
        
        # 데이터 미리보기 (처음 20개 행만 표시하여 브라우저 부하 방지)
        st.dataframe(df_preview.head(20), use_container_width=True)
        st.caption(f"💡 시스템 부하 및 대시보드 성능을 위해 검색된 {len(df)}개 레코드 중 **상위 20개**만 화면에 미리보기로 표시됩니다. 전체 데이터는 아래 다운로드 버튼을 통해 다운로드해 주세요.")
        
        # CSV 다운로드 파일 버퍼 생성 (QGIS / Excel 한글 깨짐 방지용 UTF-8-SIG 적용)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        csv_bytes = csv_buffer.getvalue().encode("utf-8-sig")
        
        # 다운로드 버튼
        st.download_button(
            label="📥 CSV 데이터 다운로드 (UTF-8-SIG)",
            data=csv_bytes,
            file_name="ecoquest_biodiversity_export.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True
        )
    else:
        st.info("선택한 필터 조건에 부합하는 생물 관찰 데이터가 데이터베이스에 없습니다.")
else:
    st.info("💡 필터 조건을 설정한 후 위의 '검색 / 조회' 버튼을 누르면 데이터 조회가 시작됩니다.")

