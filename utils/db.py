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
                    VALUES (%s, 0, 0.2)
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


def check_and_update_quest_completion(cur, user_id):
    """지정된 유저의 진행 중인 퀘스트 중 목표를 달성한 퀘스트 상태를 'completed'로 업데이트합니다."""
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
    rows = cur.fetchall()
    completed_quests = []
    for r in rows:
        if isinstance(r, dict):
            completed_quests.append(r["quest_id"])
        elif isinstance(r, (list, tuple)):
            completed_quests.append(r[0])
        else:
            completed_quests.append(r)

    for q_id in completed_quests:
        cur.execute(
            """
            UPDATE user_quest
            SET status = 'completed'
            WHERE user_id = %s AND quest_id = %s
            """,
            (user_id, q_id),
        )


def insert_discovery_transaction(
    user_id,
    candidate_ids: list[int],
    storage_url: str = _DEMO_STORAGE_URL,
    confidence_scores: list[float] | None = None,
    latitude: float | None = None,
    longitude: float | None = None
) -> dict | None:
    if not candidate_ids:
        return None

    primary_dictionary_id = candidate_ids[0]
    scores = confidence_scores or [1.0] * len(candidate_ids)

    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT 1 FROM pictures
                    WHERE user_id = %s AND candidate_dictionary_id = %s
                    """,
                    (user_id, primary_dictionary_id),
                )
                if cur.fetchone():
                    return {"duplicate": True}

                cur.execute(
                    """
                    INSERT INTO pictures (user_id, storage_url, candidate_dictionary_id, latitude, longitude)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, storage_url, primary_dictionary_id, latitude, longitude),
                )
                # pyrefly: ignore [unsupported-operation]
                picture_id = cur.fetchone()["id"]

                for cand_id, score in zip(candidate_ids, scores):
                    cur.execute(
                        """
                        INSERT INTO picture_candidates (picture_id, dictionary_id, confidence_score)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (picture_id, dictionary_id) DO NOTHING
                        """,
                        (picture_id, cand_id, score),
                    )

                # Get category_id of this dictionary entry
                cur.execute(
                    "SELECT category_id FROM dictionary WHERE id = %s",
                    (primary_dictionary_id,),
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
                    (user_id, primary_dictionary_id, user_id),
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
                check_and_update_quest_completion(cur, user_id)

                cur.execute(
                    "UPDATE users SET xp = xp + 10 WHERE id = %s",
                    (user_id,),
                )

                # 발견 성공 시 해당 생물종 이름의 동물(category_id: 3) 아이템 지급 연동
                cur.execute("SELECT name FROM dictionary WHERE id = %s", (primary_dictionary_id,))
                species_row = cur.fetchone()
                if species_row:
                    species_name = species_row["name"].strip()
                    
                    # items 테이블에 존재하는지 확인
                    cur.execute("SELECT id FROM items WHERE name = %s AND category_id = 3", (species_name,))
                    item_row = cur.fetchone()
                    if item_row:
                        item_id = item_row["id"]
                    else:
                        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM items")
                        item_id = cur.fetchone()["next_id"]
                        cur.execute(
                            "INSERT INTO items (id, name, category_id) VALUES (%s, %s, 3)",
                            (item_id, species_name)
                        )
                    
                    # 유저 인벤토리에 추가/수량 증가
                    cur.execute(
                        """
                        INSERT INTO user_inventory (user_id, item_id, quantity)
                        VALUES (%s, %s, 1)
                        ON CONFLICT (user_id, item_id)
                        DO UPDATE SET quantity = user_inventory.quantity + 1
                        """,
                        (user_id, item_id)
                    )

                cur.execute(
                    """
                    SELECT id, name, description, is_protected, category_id,
                           NULL::text AS image_url
                    FROM dictionary
                    WHERE id = %s
                    """,
                    (primary_dictionary_id,),
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
                
                # 4. Check if the newly accepted quest is already complete (e.g. has no objectives)
                check_and_update_quest_completion(cur, user_id)
                
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
                # 0. Check and update completed quests
                check_and_update_quest_completion(cur, user_id)
                
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
                # DB의 ON DELETE CASCADE 정책을 활용하여 단일 쿼리로 
                # 만료된 퀘스트 및 연관된 모든 하위 참조 테이블 데이터를 자동 삭제합니다.
                cur.execute("DELETE FROM quest WHERE expire_at < NOW()")
                conn.commit()
    except Exception as e:
        st.warning(f"만료된 퀘스트 정리 중 오류가 발생했습니다: {e}")


def fetch_random_picture_for_minigame(user_id) -> dict | None:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, storage_url, candidate_dictionary_id
                    FROM pictures
                    WHERE user_id != %s
                      AND id NOT IN (
                          SELECT picture_id FROM picture_trust WHERE user_id = %s
                      )
                    ORDER BY RANDOM()
                    LIMIT 1
                    """,
                    (user_id, user_id),
                )
                row = cur.fetchone()
                if not row:
                    return None

                pic = dict(row)

                # Fetch candidates
                cur.execute(
                    """
                    SELECT pc.dictionary_id AS id, d.name
                    FROM picture_candidates pc
                    JOIN dictionary d ON d.id = pc.dictionary_id
                    WHERE pc.picture_id = %s
                    """,
                    (pic["id"],),
                )
                pic["candidates"] = [dict(r) for r in cur.fetchall()]

                # Fetch primary candidate name
                cur.execute(
                    "SELECT name FROM dictionary WHERE id = %s",
                    (pic["candidate_dictionary_id"],),
                )
                prim = cur.fetchone()
                pic["primary_name"] = prim["name"] if prim else "알 수 없음"

                # Sign URL
                path = pic["storage_url"]
                if path and not path.startswith("http") and not path.startswith("demo://"):
                    try:
                        url = st.secrets["SUPABASE_URL"]
                        key = st.secrets["SUPABASE_KEY"]
                        client = create_client(url, key)
                        signed_res = client.storage.from_("picture").create_signed_url(path, expires_in=604800)
                        pic["storage_url"] = signed_res["signedURL"]
                    except Exception as e:
                        print(f"Error signing URL in minigame: {e}")

                return pic
    except Exception as e:
        print(f"Error fetching random picture for minigame: {e}")
        return None


def record_picture_trust(user_id, picture_id: int, selected_candidate_id: int, response_time: int) -> bool:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO picture_trust (user_id, picture_id, selected_candidate_id, response_time)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, picture_id)
                    DO UPDATE SET selected_candidate_id = EXCLUDED.selected_candidate_id,
                                  response_time = EXCLUDED.response_time
                    """,
                    (user_id, picture_id, selected_candidate_id, response_time),
                )
                # Award 10 XP directly upon minigame response completion
                cur.execute(
                    "UPDATE users SET xp = xp + 10 WHERE id = %s",
                    (user_id,),
                )
                conn.commit()
                
        # Evaluate species confirmation conditions after recording
        evaluate_and_confirm_picture(picture_id)
        return True
    except Exception as e:
        print(f"Error recording picture trust: {e}")
        return False


def check_picture_valid_for_minigame(user_id, picture_id: int) -> bool:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM pictures
                    WHERE id = %s
                      AND user_id != %s
                      AND id NOT IN (
                          SELECT picture_id FROM picture_trust WHERE user_id = %s
                      )
                    """,
                    (picture_id, user_id, user_id),
                )
                return cur.fetchone() is not None
    except Exception as e:
        print(f"Error checking picture validity for minigame: {e}")
        return False


def check_user_daily_minigame_participation(user_id) -> bool:
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM picture_trust
                    WHERE user_id = %s
                      AND created_at::date = (NOW() AT TIME ZONE 'Asia/Seoul')::date
                    LIMIT 1
                    """,
                    (user_id,),
                )
                return cur.fetchone() is not None
    except Exception as e:
        print(f"Error checking user daily minigame participation: {e}")
        return False


def calculate_binomial_p_value(n: int, k: int, p0: float = 0.25) -> float:
    """이항 가설 검정의 p-value를 계산합니다 (귀무가설 하에서 k개 이상 얻을 확률)."""
    import math
    if n == 0:
        return 1.0
    p_val = 0.0
    for x in range(k, n + 1):
        p_val += math.comb(n, x) * (p0 ** x) * ((1.0 - p0) ** (n - x))
    return p_val


def calculate_bayesian_posterior(candidates: list[dict], votes: list[dict], user_trust_map: dict) -> dict[int, float]:
    """
    각 후보 생물종에 대해 베이지안 사후 확률을 업데이트합니다.
    - candidates: [{"id": dictionary_id, "confidence_score": float}]
    - votes: [{"user_id": UUID, "selected_candidate_id": int}]
    - user_trust_map: {user_id: rho_value}
    """
    M = len(candidates)
    if M == 0:
        return {}

    # 1. Prior 정규화 (AI 예측 Confidence 활용)
    total_conf = sum(float(c["confidence_score"]) for c in candidates)
    if total_conf == 0:
        priors = {c["id"]: 1.0 / M for c in candidates}
    else:
        priors = {c["id"]: float(c["confidence_score"]) / total_conf for c in candidates}

    # 2. Likelihood 곱 계산
    likelihoods = {}
    for cand in candidates:
        s_k = cand["id"]
        lh = 1.0
        
        for vote in votes:
            u_id = vote["user_id"]
            v_i = vote["selected_candidate_id"]
            
            # 유저의 상관계수 (기록이 없거나 초기 유저면 기본값 0.2)
            rho_i = float(user_trust_map.get(u_id, 0.2))
            
            # 트롤 유저 방어: 상관계수가 음수(rho < 0.0)이면 가중치를 0.0으로 강제 고정하여 배제
            if rho_i < 0.0:
                rho_i = 0.0
            
            # 상관계수를 활용한 정답 확률 p_i 맵핑
            p_i = max(0.0, 1.0 / M + (1.0 - 1.0 / M) * rho_i)
            
            # Likelihood
            if v_i == s_k:
                lh *= p_i
            else:
                lh *= (1.0 - p_i) / max(1, M - 1)
                
        likelihoods[s_k] = lh

    # 3. Posterior 계산 (priors * likelihoods 정규화)
    denominator = sum(priors[c["id"]] * likelihoods[c["id"]] for c in candidates)
    if denominator == 0:
        return priors

    posteriors = {}
    for cand in candidates:
        s_k = cand["id"]
        posteriors[s_k] = (priors[s_k] * likelihoods[s_k]) / denominator

    return posteriors


def evaluate_and_confirm_picture(picture_id: int) -> bool:
    """
    특정 사진의 AI 분석 후보군 및 사용자 투표 결과를 종합하여 생물종 확정 여부를 판단합니다.
    최종 기준(또는 시간 경과 완화 기준)을 만족할 경우 확정(confirmed_dictionary_id 설정) 처리하고,
    기여 유저 추가 보상 및 상관계수 평판을 적응형 감마로 갱신합니다.
    """
    import datetime
    try:
        with psycopg.connect(_db_url()) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # 1. 사진 정보 조회 (created_at 추가) 및 기확정 여부 확인
                cur.execute(
                    "SELECT id, confirmed_dictionary_id, candidate_dictionary_id, created_at FROM pictures WHERE id = %s",
                    (picture_id,),
                )
                pic = cur.fetchone()
                if not pic or pic["confirmed_dictionary_id"] is not None:
                    return False
                
                # 2. AI 후보군 정보 조회
                cur.execute(
                    "SELECT dictionary_id AS id, confidence_score FROM picture_candidates WHERE picture_id = %s",
                    (picture_id,),
                )
                candidates = [dict(row) for row in cur.fetchall()]
                M = len(candidates)
                if M == 0:
                    return False
                
                # 3. 유효 사용자 투표 조회 (Spam 필터링 완화: 500ms ~ 300000ms)
                cur.execute(
                    """
                    SELECT user_id, selected_candidate_id, response_time
                    FROM picture_trust
                    WHERE picture_id = %s
                      AND response_time >= 500
                      AND response_time <= 300000
                    """,
                    (picture_id,),
                )
                votes = [dict(row) for row in cur.fetchall()]
                N = len(votes)
                
                if N == 0:
                    return False
                
                # 4. 투표에 참여한 유저들의 상관계수 신뢰 점수(trust_score) 조회
                user_ids = list(set(v["user_id"] for v in votes))
                user_trust_map = {}
                if user_ids:
                    cur.execute(
                        "SELECT id, trust_score FROM users WHERE id = ANY(%s)",
                        (user_ids,),
                    )
                    for row in cur.fetchall():
                        user_trust_map[row["id"]] = float(row["trust_score"] if row["trust_score"] is not None else 0.2)
                
                # 5. 베이지안 사후 확률 산출
                posteriors = calculate_bayesian_posterior(candidates, votes, user_trust_map)
                if not posteriors:
                    return False
                
                # 사후 확률이 가장 높은 생물종 선정
                best_candidate_id = max(posteriors, key=posteriors.get)
                best_posterior = posteriors[best_candidate_id]
                
                # 6. 1위 후보의 실제 득표수 K 계산
                K = sum(1 for v in votes if v["selected_candidate_id"] == best_candidate_id)
                consensus_ratio = float(K) / N
                
                # 7. 이항 가설 검정 p-value 산출
                p0 = 1.0 / M
                p_value = calculate_binomial_p_value(N, K, p0)
                
                # --- [확정 임계치 판단] ---
                is_confirmed = False
                
                # 안전망 확인용: 1위 후보의 AI 신뢰도 점수 조회
                ai_conf = 0.0
                for cand in candidates:
                    if cand["id"] == best_candidate_id:
                        ai_conf = float(cand["confidence_score"])
                        break
                
                # 취약점 A: 콜드 스타트 시간 경과 완화 (7일 이상 경과, N >= 1, 만장일치 C = 1.0, AI 예측 1위이며 AI 신뢰도 >= 0.8)
                pic_created = pic["created_at"]
                if pic_created:
                    # offset-naive vs offset-aware datetime 비교 일치를 위해 timezone 보정
                    if pic_created.tzinfo is None:
                        time_elapsed = datetime.datetime.now() - pic_created
                    else:
                        time_elapsed = datetime.datetime.now(datetime.timezone.utc) - pic_created
                    is_timeout = time_elapsed.days >= 7
                else:
                    is_timeout = False
                
                if is_timeout and N >= 1 and consensus_ratio == 1.0 and best_candidate_id == pic["candidate_dictionary_id"] and ai_conf >= 0.8:
                    is_confirmed = True
                    print(f"[SPECIES CONFIRMED via TIMEOUT] Picture {picture_id} -> Dictionary {best_candidate_id}")
                else:
                    # 취약점 B: 다수결 횡포 방어용 AI Confidence 기반 안전망
                    if ai_conf < 0.1:
                        # AI 신뢰도가 매우 낮은 종에 투표가 몰린 경우 규칙 강화: N >= 5, p-value < 0.01, 사후확률 >= 0.95
                        if N >= 5 and p_value < 0.01 and best_posterior >= 0.95:
                            is_confirmed = True
                    else:
                        # 일반 조건: N >= 3, p-value < 0.05, 사후확률 >= 0.95
                        if N >= 3 and p_value < 0.05 and best_posterior >= 0.95:
                            is_confirmed = True
                
                # 기준 미충족 시 확정 보류
                if not is_confirmed:
                    return False
                
                # --- [확정 및 사후 처리 실행] ---
                print(f"[SPECIES CONFIRMED] Picture {picture_id} -> Dictionary {best_candidate_id} (Posterior: {best_posterior:.4f}, p-value: {p_value:.4f})")
                
                # 1) 도감 등록 상태 업데이트
                cur.execute(
                    "UPDATE pictures SET confirmed_dictionary_id = %s WHERE id = %s",
                    (best_candidate_id, picture_id),
                )
                
                # 2) 참여자 상관계수 신뢰도 및 경험치 추가 보상 업데이트
                for vote in votes:
                    u_id = vote["user_id"]
                    v_i = vote["selected_candidate_id"]
                    
                    rho_old = float(user_trust_map.get(u_id, 0.2))
                    
                    # 적응형 감마 계산: 유저의 과거 유효 투표 횟수 n_u 조회
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM picture_trust
                        WHERE user_id = %s
                          AND response_time >= 500
                          AND response_time <= 300000
                        """,
                        (u_id,),
                    )
                    n_u = cur.fetchone()["count"]
                    
                    gamma = max(0.1, 0.5 * (0.85 ** n_u))
                    
                    if v_i == best_candidate_id:
                        # 정답 투표한 검증자: 상관계수 상향 (+1.0 방향) 및 추가 경험치 보상
                        r_current = 1.0
                        cur.execute(
                            "UPDATE users SET xp = xp + 20 WHERE id = %s",
                            (u_id,),
                        )
                    else:
                        # 오답 투표한 검증자: 상관계수 하향 (감점 완화 적용)
                        r_current = -consensus_ratio / (M - 1)
                        
                    # 상관계수 EMA 업데이트 및 [-1.0, 1.0] 클리핑
                    rho_new = (1.0 - gamma) * rho_old + gamma * r_current
                    rho_new = max(-1.0, min(1.0, rho_new))
                    
                    cur.execute(
                        "UPDATE users SET trust_score = %s WHERE id = %s",
                        (rho_new, u_id),
                    )
                
                conn.commit()
                return True
    except Exception as e:
        print(f"Error evaluating and confirming picture {picture_id}: {e}")
        return False


def fetch_research_data(
    confirmed_only: bool = False,
    category: str | None = None,
    protected_only: bool = False,
    start_date=None,
    end_date=None,
) -> list[dict]:
    import datetime
    db_url = _db_url()
    
    query_base = """
        SELECT 
            p.id AS observation_id,
            p.user_id AS uploader_id,
            COALESCE(p.confirmed_dictionary_id, p.candidate_dictionary_id) AS matched_dictionary_id,
            p.confirmed_dictionary_id IS NOT NULL AS is_confirmed,
            p.latitude,
            p.longitude,
            p.created_at AS observed_at,
            d.name AS species_name,
            d.is_protected AS is_protected,
            dc.name AS category_name
        FROM pictures p
        JOIN dictionary d ON d.id = COALESCE(p.confirmed_dictionary_id, p.candidate_dictionary_id)
        LEFT JOIN dictionary_categories dc ON dc.id = d.category_id
        WHERE p.latitude IS NOT NULL 
          AND p.longitude IS NOT NULL
    """
    
    conditions = []
    params = []
    
    if confirmed_only:
        conditions.append("p.confirmed_dictionary_id IS NOT NULL")
        
    if protected_only:
        conditions.append("d.is_protected = TRUE")
        
    if category:
        conditions.append("dc.name = %s")
        params.append(category)
        
    if start_date:
        if isinstance(start_date, str):
            start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        elif isinstance(start_date, datetime.datetime):
            start_dt = start_date
        else:
            start_dt = datetime.datetime.combine(start_date, datetime.time.min)
        conditions.append("p.created_at >= %s")
        params.append(start_dt)
        
    if end_date:
        if isinstance(end_date, str):
            end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
        elif isinstance(end_date, datetime.datetime):
            end_dt = end_date
        else:
            end_dt = datetime.datetime.combine(end_date, datetime.time.max)
        conditions.append("p.created_at <= %s")
        params.append(end_dt)
        
    if conditions:
        query_base += " AND " + " AND ".join(conditions)
        
    query_base += " ORDER BY p.id ASC"
    
    exported_data = []
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query_base, params)
                records = cur.fetchall()
                
                for row in records:
                    pic_id = row["observation_id"]
                    matched_dict_id = row["matched_dictionary_id"]
                    
                    cur.execute(
                        "SELECT dictionary_id AS id, confidence_score FROM picture_candidates WHERE picture_id = %s",
                        (pic_id,)
                    )
                    candidates_rows = cur.fetchall()
                    
                    cur.execute(
                        """
                        SELECT t.user_id, t.selected_candidate_id, t.response_time, COALESCE(u.trust_score, 0.2) AS trust_score
                        FROM picture_trust t
                        JOIN users u ON t.user_id = u.id
                        WHERE t.picture_id = %s
                          AND t.response_time >= 500
                          AND t.response_time <= 300000
                        """,
                        (pic_id,)
                    )
                    votes_rows = cur.fetchall()
                    
                    candidates = [{"id": r["id"], "confidence_score": float(r["confidence_score"])} for r in candidates_rows]
                    votes = [{"user_id": r["user_id"], "selected_candidate_id": r["selected_candidate_id"]} for r in votes_rows]
                    user_trust_map = {r["user_id"]: float(r["trust_score"]) for r in votes_rows}
                    
                    n = len(votes)
                    k = sum(1 for v in votes if v["selected_candidate_id"] == matched_dict_id)
                    M = len(candidates)
                    p0 = 1.0 / M if M > 0 else 0.25
                    
                    if M == 0:
                        confidence = 0.0
                        p_val = 1.0
                    else:
                        posteriors = calculate_bayesian_posterior(candidates, votes, user_trust_map)
                        if n == 0:
                            confidence = next((float(c["confidence_score"]) for c in candidates if c["id"] == matched_dict_id), 0.0)
                            p_val = 1.0
                        else:
                            confidence = posteriors.get(matched_dict_id, 0.0)
                            p_val = calculate_binomial_p_value(n, k, p0)
                            
                    observed_str = ""
                    if row["observed_at"]:
                        observed_str = row["observed_at"].strftime("%Y-%m-%d %H:%M:%S")
                        
                    exported_data.append({
                        "observation_id": pic_id,
                        "species_name": row["species_name"],
                        "category_name": row["category_name"] or "미분류",
                        "is_protected": row["is_protected"],
                        "latitude": row["latitude"],
                        "longitude": row["longitude"],
                        "is_confirmed": row["is_confirmed"],
                        "confidence": round(confidence, 4),
                        "p_value": round(p_val, 4),
                        "vote_count": n,
                        "observed_at": observed_str
                    })
    except Exception as e:
        print(f"Error fetching research data: {e}")
    return exported_data


def fetch_admin_statistics() -> dict:
    db_url = _db_url()
    stats = {
        "total_users": 0,
        "total_pictures": 0,
        "confirmed_pictures": 0,
        "pending_pictures": 0,
        "restricted_users": 0
    }
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM users")
                stats["total_users"] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM pictures")
                stats["total_pictures"] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM pictures WHERE confirmed_dictionary_id IS NOT NULL")
                stats["confirmed_pictures"] = cur.fetchone()[0]
                
                stats["pending_pictures"] = stats["total_pictures"] - stats["confirmed_pictures"]
                
                cur.execute("SELECT COUNT(*) FROM users WHERE trust_score <= -0.2")
                stats["restricted_users"] = cur.fetchone()[0]
    except Exception as e:
        print(f"Error fetching admin statistics: {e}")
    return stats


