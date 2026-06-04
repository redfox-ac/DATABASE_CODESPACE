import uuid

import psycopg
import streamlit as st
from psycopg.rows import dict_row
from supabase import create_client

DEFAULT_MAX_XP = 200
_DEMO_STORAGE_URL = "demo://ecoquest/collection"


def _db_url() -> str:
    return st.secrets["SUPABASE_DB_URL"]


def upload_picture_to_supabase(file_data: bytes, file_name: str) -> str:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    client = create_client(url, key)
    
    client.storage.from_("picture").upload(
        file=file_data,
        path=file_name,
        file_options={"content-type": "image/jpeg"}
    )
    
    return file_name


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
                        p.storage_url AS image_url
                    FROM pictures p
                    JOIN dictionary d
                        ON d.id = COALESCE(p.confirmed_dictionary_id, p.candidate_dictionary_id)
                    WHERE p.user_id = %s
                      AND COALESCE(p.confirmed_dictionary_id, p.candidate_dictionary_id) IS NOT NULL
                    ORDER BY p.id DESC
                    """,
                    (user_id,),
                )
                rows = [dict(row) for row in cur.fetchall()]
                
                if rows:
                    url = st.secrets["SUPABASE_URL"]
                    key = st.secrets["SUPABASE_KEY"]
                    client = create_client(url, key)
                    for r in rows:
                        path = r.get("image_url")
                        if path and not path.startswith("http") and not path.startswith("demo://"):
                            try:
                                signed_res = client.storage.from_("picture").create_signed_url(path, expires_in=604800)
                                r["image_url"] = signed_res["signedURL"]
                            except Exception as e:
                                print(f"Error generating signed URL for {path}: {e}")
                return rows
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


def insert_discovery_transaction(user_id, dictionary_id: int, storage_url: str = _DEMO_STORAGE_URL) -> dict | None:
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
                    (user_id, storage_url, dictionary_id),
                )

                # Get category_id of this dictionary entry
                cur.execute(
                    "SELECT category_id FROM dictionary WHERE id = %s",
                    (dictionary_id,),
                )
                dict_entry = cur.fetchone()
                category_id = dict_entry["category_id"] if dict_entry else None

                # Update quest progress for active quests
                # Update specific species progress
                cur.execute(
                    """
                    UPDATE quest_progress_dictionary
                    SET current_count = current_count + 1
                    WHERE user_id = %s AND dictionary_id = %s
                      AND quest_id IN (
                          SELECT quest_id FROM user_quest WHERE user_id = %s AND status = 'in_progress'
                      )
                    """,
                    (user_id, dictionary_id, user_id),
                )

                # Update category progress
                if category_id is not None:
                    cur.execute(
                        """
                        UPDATE quest_progress_dictionary_categories
                        SET current_count = current_count + 1
                        WHERE user_id = %s AND category_id = %s
                          AND quest_id IN (
                              SELECT quest_id FROM user_quest WHERE user_id = %s AND status = 'in_progress'
                          )
                        """,
                        (user_id, category_id, user_id),
                    )

                # Check if any active quests are now completed
                cur.execute(
                    """
                    SELECT uq.quest_id
                    FROM user_quest uq
                    WHERE uq.user_id = %s AND uq.status = 'in_progress'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM target_dictionary td
                          LEFT JOIN quest_progress_dictionary qpd
                            ON qpd.user_id = uq.user_id
                           AND qpd.quest_id = uq.quest_id
                           AND qpd.dictionary_id = td.dictionary_id
                          WHERE td.quest_id = uq.quest_id
                            AND COALESCE(qpd.current_count, 0) < td.target_count
                      )
                      AND NOT EXISTS (
                          SELECT 1
                          FROM target_dictionary_categories tdc
                          LEFT JOIN quest_progress_dictionary_categories qpdc
                            ON qpdc.user_id = uq.user_id
                           AND qpdc.quest_id = uq.quest_id
                           AND qpdc.category_id = tdc.category_id
                          WHERE tdc.quest_id = uq.quest_id
                            AND COALESCE(qpdc.current_count, 0) < tdc.target_count
                      )
                    """,
                    (user_id,),
                )
                completed_quests = [r["quest_id"] for r in cur.fetchall()]

                for q_id in completed_quests:
                    cur.execute(
                        """
                        UPDATE user_quest
                        SET status = 'completed'
                        WHERE user_id = %s AND quest_id = %s
                        """,
                        (user_id, q_id),
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
    except Exception as e:
        st.error(f"생물 수집을 저장하는 데 실패했습니다: {e}")
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


def fetch_terrarium_layout(user_id) -> list[dict]:
    """모든 슬롯 정의와 유저 장착 상태를 합쳐 반환합니다."""
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        ts.id AS slot_id,
                        ts.name AS slot_name,
                        ts.description AS slot_description,
                        ts.category_id AS slot_category_id,
                        ic_slot.name AS slot_category_name,
                        ut.item_id AS equipped_item_id,
                        i.name AS equipped_item_name
                    FROM terrarium_slot ts
                    LEFT JOIN items_category ic_slot
                        ON ic_slot.id = ts.category_id
                    LEFT JOIN user_terrarium ut
                        ON ut.slot_id = ts.id AND ut.user_id = %s
                    LEFT JOIN items i ON i.id = ut.item_id
                    ORDER BY ts.id
                    """,
                    (user_id,),
                )
                return [dict(row) for row in cur.fetchall()]
    except Exception:
        st.warning("테라리움 슬롯 데이터를 불러오는 데 실패했습니다.")
        return []


def fetch_user_inventory(user_id) -> list[dict]:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        ui.id AS inventory_id,
                        ui.item_id,
                        ui.quantity,
                        i.name AS item_name,
                        i.category_id,
                        ic.name AS category_name
                    FROM user_inventory ui
                    JOIN items i ON i.id = ui.item_id
                    LEFT JOIN items_category ic ON ic.id = i.category_id
                    WHERE ui.user_id = %s AND ui.quantity > 0
                    ORDER BY ic.name NULLS LAST, i.name
                    """,
                    (user_id,),
                )
                return [dict(row) for row in cur.fetchall()]
    except Exception:
        st.warning("인벤토리를 불러오는 데 실패했습니다.")
        return []


def equip_terrarium_item(user_id, slot_id: int, item_id: int) -> str | None:
    """슬롯에 아이템을 장착합니다. 성공 시 None, 실패 시 오류 메시지."""
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT category_id FROM terrarium_slot WHERE id = %s
                    """,
                    (slot_id,),
                )
                slot = cur.fetchone()
                if not slot:
                    return "존재하지 않는 슬롯입니다."

                cur.execute(
                    """
                    SELECT 1
                    FROM user_inventory ui
                    JOIN items i ON i.id = ui.item_id
                    WHERE ui.user_id = %s
                      AND ui.item_id = %s
                      AND ui.quantity > 0
                      AND i.category_id = %s
                    """,
                    (user_id, item_id, slot["category_id"]),
                )
                if not cur.fetchone():
                    return "인벤토리에 없거나 이 슬롯에 맞지 않는 아이템입니다."

                cur.execute(
                    """
                    INSERT INTO user_terrarium (user_id, slot_id, item_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, slot_id)
                    DO UPDATE SET item_id = EXCLUDED.item_id
                    """,
                    (user_id, slot_id, item_id),
                )
                conn.commit()
                return None
    except Exception:
        st.error("아이템 장착에 실패했습니다.")
        return "아이템 장착에 실패했습니다."


def unequip_terrarium_item(user_id, slot_id: int) -> str | None:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM user_terrarium
                    WHERE user_id = %s AND slot_id = %s
                    """,
                    (user_id, slot_id),
                )
                conn.commit()
                return None
    except Exception:
        st.error("아이템 해제에 실패했습니다.")
        return "아이템 해제에 실패했습니다."


def fetch_available_quests(user_id) -> list[dict]:
    """유저가 수락하지 않은 퀘스트 목록을 목표 및 보상 정보와 함께 조회합니다."""
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # 1. Fetch quests not accepted by the user
                cur.execute(
                    """
                    SELECT q.id, q.description, q.reward_xp
                    FROM quest q
                    WHERE NOT EXISTS (
                        SELECT 1 FROM user_quest uq
                        WHERE uq.quest_id = q.id AND uq.user_id = %s
                    )
                    ORDER BY q.id
                    """,
                    (user_id,),
                )
                quests = [dict(row) for row in cur.fetchall()]

                # 2. For each quest, get its targets and rewards
                for q in quests:
                    q_id = q["id"]
                    
                    # Fetch species targets
                    cur.execute(
                        """
                        SELECT td.dictionary_id, td.target_count, d.name AS species_name
                        FROM target_dictionary td
                        JOIN dictionary d ON d.id = td.dictionary_id
                        WHERE td.quest_id = %s
                        """,
                        (q_id,),
                    )
                    q["target_species"] = [dict(r) for r in cur.fetchall()]

                    # Fetch category targets
                    cur.execute(
                        """
                        SELECT tdc.category_id, tdc.target_count, c.name AS category_name
                        FROM target_dictionary_categories tdc
                        JOIN dictionary_categories c ON c.id = tdc.category_id
                        WHERE tdc.quest_id = %s
                        """,
                        (q_id,),
                    )
                    q["target_categories"] = [dict(r) for r in cur.fetchall()]

                    # Fetch items rewards
                    cur.execute(
                        """
                        SELECT qr.item_id, qr.amount, i.name AS item_name
                        FROM quest_reward qr
                        JOIN items i ON i.id = qr.item_id
                        WHERE qr.quest_id = %s
                        """,
                        (q_id,),
                    )
                    q["rewards"] = [dict(r) for r in cur.fetchall()]

                return quests
    except Exception:
        st.warning("수락 가능한 퀘스트 목록을 불러오는 데 실패했습니다.")
        return []


def accept_quest(user_id, quest_id: int) -> bool:
    """퀘스트를 수락하여 user_quest 및 진행도 추적 테이블(quest_progress~)에 초기 데이터를 삽입합니다."""
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor() as cur:
                # 1. Insert user_quest row
                cur.execute(
                    """
                    INSERT INTO user_quest (user_id, quest_id, status)
                    VALUES (%s, %s, 'in_progress')
                    ON CONFLICT (user_id, quest_id) DO NOTHING
                    """,
                    (user_id, quest_id),
                )
                
                # 2. Insert target_dictionary targets into progress with count = 0
                cur.execute(
                    """
                    INSERT INTO quest_progress_dictionary (user_id, quest_id, dictionary_id, current_count)
                    SELECT %s, %s, dictionary_id, 0
                    FROM target_dictionary
                    WHERE quest_id = %s
                    ON CONFLICT (user_id, quest_id, dictionary_id) DO NOTHING
                    """,
                    (user_id, quest_id, quest_id),
                )

                # 3. Insert target_dictionary_categories targets into progress with count = 0
                cur.execute(
                    """
                    INSERT INTO quest_progress_dictionary_categories (user_id, quest_id, category_id, current_count)
                    SELECT %s, %s, category_id, 0
                    FROM target_dictionary_categories
                    WHERE quest_id = %s
                    ON CONFLICT (user_id, quest_id, category_id) DO NOTHING
                    """,
                    (user_id, quest_id, quest_id),
                )
                
                conn.commit()
                return True
    except Exception as e:
        st.error(f"퀘스트 수락에 실패했습니다: {e}")
        return False


def fetch_user_quests(user_id) -> list[dict]:
    """유저가 수락한 퀘스트(진행 중, 완료, 수령 완료) 목록을 진행 상황 및 보상 정보와 함께 가져옵니다."""
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # Fetch user quests
                cur.execute(
                    """
                    SELECT uq.quest_id, uq.status, q.description, q.reward_xp, q.expire_at
                    FROM user_quest uq
                    JOIN quest q ON q.id = uq.quest_id
                    WHERE uq.user_id = %s
                    ORDER BY q.expire_at ASC, uq.quest_id DESC
                    """,
                    (user_id,),
                )
                user_quests = [dict(row) for row in cur.fetchall()]

                for uq in user_quests:
                    q_id = uq["quest_id"]

                    # Fetch species targets with current progress count
                    cur.execute(
                        """
                        SELECT td.dictionary_id, td.target_count, d.name AS species_name,
                               COALESCE(qpd.current_count, 0) AS current_count
                        FROM target_dictionary td
                        JOIN dictionary d ON d.id = td.dictionary_id
                        LEFT JOIN quest_progress_dictionary qpd
                          ON qpd.user_id = %s
                         AND qpd.quest_id = td.quest_id
                         AND qpd.dictionary_id = td.dictionary_id
                        WHERE td.quest_id = %s
                        """,
                        (user_id, q_id),
                    )
                    uq["target_species"] = [dict(r) for r in cur.fetchall()]

                    # Fetch category targets with current progress count
                    cur.execute(
                        """
                        SELECT tdc.category_id, tdc.target_count, c.name AS category_name,
                               COALESCE(qpdc.current_count, 0) AS current_count
                        FROM target_dictionary_categories tdc
                        JOIN dictionary_categories c ON c.id = tdc.category_id
                        LEFT JOIN quest_progress_dictionary_categories qpdc
                          ON qpdc.user_id = %s
                         AND qpdc.quest_id = tdc.quest_id
                         AND qpdc.category_id = tdc.category_id
                        WHERE tdc.quest_id = %s
                        """,
                        (user_id, q_id),
                    )
                    uq["target_categories"] = [dict(r) for r in cur.fetchall()]

                    # Fetch items rewards
                    cur.execute(
                        """
                        SELECT qr.item_id, qr.amount, i.name AS item_name
                        FROM quest_reward qr
                        JOIN items i ON i.id = qr.item_id
                        WHERE qr.quest_id = %s
                        """,
                        (q_id,),
                    )
                    uq["rewards"] = [dict(r) for r in cur.fetchall()]

                return user_quests
    except Exception:
        st.warning("유저 퀘스트 목록을 불러오는 데 실패했습니다.")
        return []


def claim_quest_reward(user_id, quest_id: int) -> dict | None:
    """퀘스트 보상을 지급하고 user_quest 상태를 'claimed'로 업데이트합니다. 획득 보상 반환."""
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # 1. Verify quest state
                cur.execute(
                    """
                    SELECT status FROM user_quest
                    WHERE user_id = %s AND quest_id = %s
                    """,
                    (user_id, quest_id),
                )
                row = cur.fetchone()
                if not row:
                    return {"success": False, "message": "수락되지 않은 퀘스트입니다."}
                if row["status"] != "completed":
                    if row["status"] == "claimed":
                        return {"success": False, "message": "이미 보상을 수령한 퀘스트입니다."}
                    return {"success": False, "message": "아직 완료되지 않은 퀘스트입니다."}

                # 2. Get quest reward details
                cur.execute(
                    """
                    SELECT id, description, reward_xp FROM quest WHERE id = %s
                    """,
                    (quest_id,),
                )
                quest = cur.fetchone()
                if not quest:
                    return {"success": False, "message": "존재하지 않는 퀘스트입니다."}

                cur.execute(
                    """
                    SELECT qr.item_id, qr.amount, i.name AS item_name
                    FROM quest_reward qr
                    JOIN items i ON i.id = qr.item_id
                    WHERE qr.quest_id = %s
                    """,
                    (quest_id,),
                )
                rewards = [dict(r) for r in cur.fetchall()]

                # 3. Apply XP reward
                reward_xp = quest.get("reward_xp", 0)
                cur.execute(
                    "UPDATE users SET xp = xp + %s WHERE id = %s",
                    (reward_xp, user_id),
                )

                # 4. Apply Item rewards
                acquired_items = []
                for reward in rewards:
                    item_id = reward["item_id"]
                    amount = reward["amount"]
                    cur.execute(
                        """
                        INSERT INTO user_inventory (user_id, item_id, quantity)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, item_id)
                        DO UPDATE SET quantity = user_inventory.quantity + EXCLUDED.quantity
                        """,
                        (user_id, item_id, amount),
                    )
                    acquired_items.append(f"{reward['item_name']} {amount}개")

                # 5. Set user_quest status to 'claimed'
                cur.execute(
                    """
                    UPDATE user_quest
                    SET status = 'claimed'
                    WHERE user_id = %s AND quest_id = %s
                    """,
                    (user_id, quest_id),
                )

                conn.commit()
                return {
                    "success": True,
                    "reward_xp": reward_xp,
                    "items": acquired_items,
                    "message": "보상 수령 완료!"
                }
    except Exception as e:
        st.error(f"보상 수령 처리 중 오류가 발생했습니다: {e}")
        return {"success": False, "message": "보상 수령 처리 중 오류가 발생했습니다."}


def fetch_all_categories() -> list[dict]:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT id, name, description FROM dictionary_categories ORDER BY name")
                return [dict(row) for row in cur.fetchall()]
    except Exception:
        st.warning("분류 목록을 불러오는 데 실패했습니다.")
        return []


def fetch_paged_dictionary_with_discovery(
    user_id,
    # pyrefly: ignore [bad-function-definition]
    search_query: str = None,
    # pyrefly: ignore [bad-function-definition]
    category_id: int = None,
    discovery_filter: str = "전체",  # "전체", "발견 완료", "미발견"
    limit: int = 24,
    offset: int = 0
) -> tuple[list[dict], int]:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                conditions = []
                params = [user_id]
                
                if search_query and search_query.strip():
                    conditions.append("d.name ILIKE %s")
                    params.append(f"%{search_query.strip()}%")
                    
                if category_id is not None:
                    conditions.append("d.category_id = %s")
                    params.append(category_id)
                    
                if discovery_filter == "발견 완료":
                    conditions.append("p.id IS NOT NULL")
                elif discovery_filter == "미발견":
                    conditions.append("p.id IS NULL")
                    
                where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
                
                # Get total count
                count_query = f"""
                    SELECT COUNT(DISTINCT d.id) 
                    FROM dictionary d
                    LEFT JOIN pictures p
                        ON p.user_id = %s
                       AND COALESCE(p.confirmed_dictionary_id, p.candidate_dictionary_id) = d.id
                    {where_clause}
                """
                # pyrefly: ignore [bad-argument-type]
                cur.execute(count_query, params)
                row = cur.fetchone()
                total_count = list(row.values())[0] if row else 0
                
                # Get paged data
                data_query = f"""
                    SELECT * FROM (
                        SELECT DISTINCT ON (d.id)
                            d.id AS dictionary_id,
                            d.name,
                            d.description,
                            d.is_protected,
                            d.category_id,
                            p.storage_url AS image_url,
                            d.name AS sort_name
                        FROM dictionary d
                        LEFT JOIN pictures p
                            ON p.user_id = %s
                           AND COALESCE(p.confirmed_dictionary_id, p.candidate_dictionary_id) = d.id
                        {where_clause}
                        ORDER BY d.id, p.id DESC
                    ) sub
                    ORDER BY sort_name ASC
                    LIMIT %s OFFSET %s
                """
                
                data_params = params + [limit, offset]
                # pyrefly: ignore [bad-argument-type]
                cur.execute(data_query, data_params)
                rows = [dict(row) for row in cur.fetchall()]
                
                if rows:
                    url = st.secrets["SUPABASE_URL"]
                    key = st.secrets["SUPABASE_KEY"]
                    client = create_client(url, key)
                    for r in rows:
                        path = r.get("image_url")
                        if path and not path.startswith("http") and not path.startswith("demo://"):
                            try:
                                signed_res = client.storage.from_("picture").create_signed_url(path, expires_in=604800)
                                r["image_url"] = signed_res["signedURL"]
                            except Exception as e:
                                print(f"Error generating signed URL for {path}: {e}")
                                
                return rows, total_count
    except Exception as e:
        st.warning(f"도감 데이터를 불러오는 데 실패했습니다: {e}")
        return [], 0


def cleanup_expired_quests() -> None:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor() as cur:
                # 1. Get expired quest IDs
                cur.execute("SELECT id FROM quest WHERE expire_at < NOW()")
                expired_ids = [row[0] for row in cur.fetchall()]
                
                if expired_ids:
                    # 2. Delete progress details first due to foreign key constraints (NO ACTION)
                    cur.execute(
                        "DELETE FROM quest_progress_dictionary WHERE quest_id = ANY(%s)",
                        (expired_ids,),
                    )
                    cur.execute(
                        "DELETE FROM quest_progress_dictionary_categories WHERE quest_id = ANY(%s)",
                        (expired_ids,),
                    )
                    # 3. Delete user_quest mapping
                    cur.execute(
                        "DELETE FROM user_quest WHERE quest_id = ANY(%s)",
                        (expired_ids,),
                    )
                    # 4. Delete quest rewards
                    cur.execute(
                        "DELETE FROM quest_reward WHERE quest_id = ANY(%s)",
                        (expired_ids,),
                    )
                    # 5. Delete quest target species/categories
                    cur.execute(
                        "DELETE FROM target_dictionary WHERE quest_id = ANY(%s)",
                        (expired_ids,),
                    )
                    cur.execute(
                        "DELETE FROM target_dictionary_categories WHERE quest_id = ANY(%s)",
                        (expired_ids,),
                    )
                    # 6. Delete quest itself
                    cur.execute(
                        "DELETE FROM quest WHERE id = ANY(%s)",
                        (expired_ids,),
                    )
                    conn.commit()
    except Exception as e:
        st.warning(f"만료된 퀘스트 정리 중 오류가 발생했습니다: {e}")

