from sqlalchemy import text
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Supabase 연결 테스트", page_icon="🗄️")
st.title("Supabase DB 연결 테스트")

conn = st.connection("supabase_db", type="sql")

st.subheader("1. 연결 확인")

try:
    result = conn.query("SELECT current_database() AS db_name, now() AS server_time;")
    st.success("DB 연결 성공")
    st.dataframe(result)
except Exception as e:
    st.error(f"DB 연결 실패: {e}")
    st.stop()

st.subheader("2. 테스트 테이블 생성")

try:
    with conn.session as s:
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS streamlit_test (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """))
        s.commit()
    st.success("테이블 확인/생성 완료")
except Exception as e:
    st.error(f"테이블 생성 실패: {e}")
    st.stop()

st.subheader("3. 데이터 입력")

name = st.text_input("이름 입력", placeholder="예: Gil-Dong")

if st.button("저장"):
    if not name.strip():
        st.warning("이름을 입력해줘.")
    else:
        try:
            with conn.session as s:
                s.execute(
                    text("INSERT INTO streamlit_test (name) VALUES (:name)"),
                    {"name": name.strip()}
                )
                s.commit()
            st.success("저장 완료")
            st.rerun()
        except Exception as e:
            st.error(f"저장 실패: {e}")

st.subheader("4. 저장된 데이터 조회")

try:
    df = conn.query("""
        SELECT id, name, created_at
        FROM streamlit_test
        ORDER BY id DESC;
    """, ttl=0)

    if df.empty:
        st.info("아직 저장된 데이터가 없습니다.")
    else:
        st.dataframe(df, use_container_width=True)
except Exception as e:
    st.error(f"조회 실패: {e}")
