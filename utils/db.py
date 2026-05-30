import uuid

import psycopg
import streamlit as st
from psycopg.rows import dict_row

DEFAULT_MAX_XP = 200
_DEMO_STORAGE_URL = "demo://ecoquest/collection"


def _db_url() -> str:
    return st.secrets["SUPABASE_DB_URL"]


def nickname_to_user_id(nickname: str) -> uuid.UUID:
    """닉네임마다 동일한 UUID를 생성해 재로그인 시 같은 유저로 인식합니다."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"ecoquest:{nickname.strip().lower()}")


def _enrich_user(row: dict, nickname: str) -> dict:
    user = dict(row)
    user["nickname"] = nickname
    user["max_xp"] = DEFAULT_MAX_XP
    if isinstance(user.get("id"), uuid.UUID):
        user["id"] = user["id"]
    return user


def authenticate_user(nickname: str) -> dict | None:
    nickname = nickname.strip()
    if not nickname:
        return None

    user_id = nickname_to_user_id(nickname)
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT id, xp, trust_score, created_at FROM users WHERE id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                if row:
                    return _enrich_user(row, nickname)

                cur.execute(
                    """
                    INSERT INTO users (id, xp, trust_score)
                    VALUES (%s, 0, 0)
                    RETURNING id, xp, trust_score, created_at
                    """,
                    (user_id,),
                )
                new_row = cur.fetchone()
                conn.commit()
                if new_row:
                    return _enrich_user(new_row, nickname)
                return None
    except Exception:
        st.error("로그인 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
        return None


def fetch_user(user_id, nickname: str | None = None) -> dict | None:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT id, xp, trust_score, created_at FROM users WHERE id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                nick = nickname or ""
                return _enrich_user(row, nick)
    except Exception:
        st.warning("프로필 정보를 불러오는 데 실패했습니다.")
        return None


def fetch_user_collection(user_id) -> list[dict]:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        p.id AS collection_id,
                        p.user_id,
                        COALESCE(p.confirmed_dictionary_id, p.candidate_dictionary_id) AS dictionary_id,
                        d.name,
                        d.description,
                        d.is_protected,
                        d.category_id,
                        NULL::text AS image_url
                    FROM pictures p
                    JOIN dictionary d
                        ON d.id = COALESCE(p.confirmed_dictionary_id, p.candidate_dictionary_id)
                    WHERE p.user_id = %s
                      AND COALESCE(p.confirmed_dictionary_id, p.candidate_dictionary_id) IS NOT NULL
                    ORDER BY p.id DESC
                    """,
                    (user_id,),
                )
                return [dict(row) for row in cur.fetchall()]
    except Exception:
        st.warning("수집 도감 데이터를 불러오는 데 실패했습니다.")
        return []


def fetch_dictionary_ids() -> list[int]:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM dictionary")
                return [row[0] for row in cur.fetchall()]
    except Exception:
        st.warning("도감 목록을 불러오는 데 실패했습니다.")
        return []


def fetch_dictionary_entry(dictionary_id: int) -> dict | None:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, name, description, is_protected, category_id,
                           NULL::text AS image_url
                    FROM dictionary
                    WHERE id = %s
                    """,
                    (dictionary_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception:
        st.warning("생물 정보를 불러오는 데 실패했습니다.")
        return None


def fetch_all_dictionary() -> list[dict]:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, name, description, is_protected, category_id,
                           NULL::text AS image_url
                    FROM dictionary
                    ORDER BY name
                    """
                )
                return [dict(row) for row in cur.fetchall()]
    except Exception:
        st.warning("도감 마스터 데이터를 불러오는 데 실패했습니다.")
        return []


def insert_discovery_transaction(user_id, dictionary_id: int) -> dict | None:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT 1 FROM pictures
                    WHERE user_id = %s AND candidate_dictionary_id = %s
                    """,
                    (user_id, dictionary_id),
                )
                if cur.fetchone():
                    return {"duplicate": True}

                cur.execute(
                    """
                    INSERT INTO pictures (user_id, storage_url, candidate_dictionary_id)
                    VALUES (%s, %s, %s)
                    """,
                    (user_id, _DEMO_STORAGE_URL, dictionary_id),
                )
                cur.execute(
                    "UPDATE users SET xp = xp + 10 WHERE id = %s",
                    (user_id,),
                )
                cur.execute(
                    """
                    SELECT id, name, description, is_protected, category_id,
                           NULL::text AS image_url
                    FROM dictionary
                    WHERE id = %s
                    """,
                    (dictionary_id,),
                )
                entry = cur.fetchone()
                conn.commit()
                if entry:
                    return dict(entry)
                return None
    except Exception:
        st.error("생물 수집을 저장하는 데 실패했습니다.")
        return None


def fetch_quests() -> list[dict]:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, description, reward_xp
                    FROM quest
                    ORDER BY id
                    """
                )
                return [dict(row) for row in cur.fetchall()]
    except Exception:
        st.warning("퀘스트 목록을 불러오는 데 실패했습니다.")
        return []


def fetch_terrarium_slots(user_id) -> list[dict]:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        ts.id,
                        ut.user_id,
                        ts.name,
                        COALESCE(ic.name, '') AS equipped_category
                    FROM user_terrarium ut
                    JOIN terrarium_slot ts ON ts.id = ut.slot_id
                    LEFT JOIN items i ON i.id = ut.item_id
                    LEFT JOIN items_category ic ON ic.id = i.category_id
                    WHERE ut.user_id = %s
                    ORDER BY ts.id
                    """,
                    (user_id,),
                )
                return [dict(row) for row in cur.fetchall()]
    except Exception:
        st.warning("테라리움 슬롯 데이터를 불러오는 데 실패했습니다.")
        return []
