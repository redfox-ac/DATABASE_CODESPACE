import sys
import os
import time
import psycopg
from psycopg.rows import dict_row
import uuid
import streamlit as st
from google import genai
from PIL import Image
import io
import random
from pydantic import BaseModel, Field

# Streamlit secrets 로드를 위한 모의 환경 셋업 및 패스 지정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from utils.db import (
    _db_url,
    authenticate_user,
    upload_picture_to_supabase,
    insert_discovery_transaction,
    record_picture_trust,
    fetch_user,
    calculate_binomial_p_value,
    calculate_bayesian_posterior,
    fetch_random_picture_for_minigame,
)
from supabase import create_client

def cleanup_real_test_data(user_ids, picture_id, storage_filename):
    """테스트용으로 적재했던 Supabase Storage 파일 및 DB 유저/사진 데이터를 완벽히 삭제합니다."""
    print("\n" + "="*50)
    print("🧹 [CLEANUP] 테스트 데이터 정리 중...")
    print("="*50)
    
    db_url = _db_url()
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        client = create_client(url, key)
        print(f" - Supabase Storage에서 파일 제거: {storage_filename}")
        client.storage.from_("picture").remove([storage_filename])
    except Exception as e:
        print(f"⚠️ Storage 파일 정리 실패: {e}")
        
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                if picture_id:
                    print(f" - Pictures 레코드 제거 (ID: {picture_id}) 및 연관 투표/후보 자동 연쇄 삭제")
                    cur.execute("DELETE FROM pictures WHERE id = %s", (picture_id,))
                
                if user_ids:
                    print(f" - 테스트 유저 레코드 제거: {user_ids}")
                    cur.execute("DELETE FROM users WHERE id = ANY(%s)", (user_ids,))
                
                conn.commit()
        print("🎉 [CLEANUP] 모든 테스트 데이터가 안전하게 정리되었습니다.")
    except Exception as e:
        print(f"⚠️ DB 데이터 정리 실패: {e}")


class SpeciesCandidate(BaseModel):
    name: str = Field(description="동물의 한국어 생물종 이름")
    confidence_score: float = Field(description="이 분석 결과에 대한 AI의 확신 점수 (0.0-1.0 사이)")


class ImageAnalysisResult(BaseModel):
    candidates: list[SpeciesCandidate] = Field(
        description="분석 결과로 추정되는 생물종 후보 목록. 이미지의 생물이 확실하더라도 추후 검증을 위해 반드시 유사종이나 가능성이 있는 후보종들을 포함하여 최소 2개, 최대 4개까지 신뢰도가 높은 순으로 제공해야 합니다."
    )


def compress_image(uploaded_file, max_size_bytes=2 * 1024 * 1024) -> io.BytesIO:
    """실제 pages/1_home.py 의 이미지 압축 기능과 100% 동일하게 구현된 압축 유틸리티"""
    img = Image.open(uploaded_file)
    
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
        
    quality = 90
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=quality)
    
    if len(output.getvalue()) <= max_size_bytes:
        output.seek(0)
        return output
        
    width, height = img.size
    for attempt in range(10):
        for q in [85, 80, 75, 70]:
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=q)
            if len(output.getvalue()) <= max_size_bytes:
                output.seek(0)
                return output
        
        width = int(width * 0.8)
        height = int(height * 0.8)
        if width < 800 or height < 800:
            break
        img = img.resize((width, height), Image.Resampling.LANCZOS)
        
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=60)
    output.seek(0)
    return output


def analyze_image_via_gemini(img_path: str):
    """지정된 이미지 경로의 파일을 로드하여 Gemini API로 분석한 뒤 에코퀘스트 도감과 매칭된 후보 목록을 반환합니다."""
    if "GEMINI_API_KEY" not in st.secrets:
        raise ValueError("GEMINI_API_KEY가 st.secrets에 설정되지 않았습니다.")
    
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    config = genai.types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ImageAnalysisResult,
        temperature=0.1
    )
    
    print(f"📷 [AI 분석] '{os.path.basename(img_path)}' 이미지 분석 중...")
    with open(img_path, "rb") as f:
        img_bytes = f.read()
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            Image.open(io.BytesIO(img_bytes)), 
            "이 이미지를 정밀하게 분석해서 지정된 형식의 JSON 데이터로 출력해줘. 이미지가 아주 확실하더라도, 나중의 검증을 위해 형태적으로 가장 유사하거나 가능성이 있는 구체적인 한국어 생물종 후보를 포함하여 **최대 4개**의 후보 목록(candidates)을 항상 채워서 반환해줘. 포괄적인 분류명(예: 벌, 도마뱀)보다는 구체적인 한국어 국명(예: 쌍살벌, 장수도마뱀)을 우선적으로 사용해줘."
        ],
        config=config,
    )
    
    candidates = response.parsed.candidates if response.parsed else []
    if not candidates:
        raise ValueError("이미지에서 분석된 생물종 후보가 없습니다.")
        
    db_url = _db_url()
    matched_candidates = []
    
    with psycopg.connect(db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, name, is_protected FROM dictionary")
            dict_list = cur.fetchall()
            
            for cand in candidates:
                matched = next((item for item in dict_list if item["name"].strip() == cand.name.strip()), None)
                if matched:
                    matched_candidates.append({
                        "id": matched["id"],
                        "name": matched["name"],
                        "confidence_score": cand.confidence_score,
                        "is_protected": matched["is_protected"]
                    })
                    
    if not matched_candidates:
        raise ValueError(f"분석된 생물종 후보들({[c.name for c in candidates]})이 도감에 등록되어 있지 않습니다.")
        
    # 만약 매칭된 후보가 4개 미만인 경우 도감에서 무작위 오답 후보군을 채워 4개 후보를 보장합니다.
    candidate_ids = [c["id"] for c in matched_candidates]
    if len(matched_candidates) < 4:
        others = [d for d in dict_list if d["id"] not in candidate_ids]
        needed = 4 - len(matched_candidates)
        wrong = random.sample(others, min(needed, len(others)))
        for w in wrong:
            matched_candidates.append({
                "id": w["id"],
                "name": w["name"],
                "confidence_score": 0.01,
                "is_protected": w.get("is_protected", False)
            })

    matched_candidates.sort(key=lambda x: x["confidence_score"], reverse=True)
    return matched_candidates[:4]


def print_intermediate_status(picture_id, dict_ids, dict_names, user_id_to_nickname=None):
    """현재까지 누적된 투표 상황을 DB에서 조회하여 베이지안 사후 확률 및 p-value를 계산하고 터미널에 상세 출력합니다."""
    if user_id_to_nickname is None:
        user_id_to_nickname = {}
    db_url = _db_url()
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # 1. AI 후보군 조회
                cur.execute(
                    "SELECT dictionary_id AS id, confidence_score FROM picture_candidates WHERE picture_id = %s",
                    (picture_id,),
                )
                candidates = [dict(row) for row in cur.fetchall()]
                
                # 2. 현재 투표 현황 조회
                cur.execute(
                    """
                    SELECT t.user_id, t.selected_candidate_id, t.response_time, u.trust_score
                    FROM picture_trust t
                    JOIN users u ON t.user_id = u.id
                    WHERE t.picture_id = %s
                      AND t.response_time >= 500
                      AND t.response_time <= 300000
                    """,
                    (picture_id,),
                )
                votes = [dict(row) for row in cur.fetchall()]
                
                N = len(votes)
                print(f"\n   📊 [중간 연산 분석] 현재 유효 투표수 N = {N}")
                if N == 0:
                    print("     - 투표 데이터가 아직 없습니다.")
                    return
                
                # dictionary_id -> name 매핑
                dict_name_map = dict(zip(dict_ids, dict_names))
                
                # 누적 투표 이력 상세 출력
                print("   [누적 투표 이력]")
                for v in votes:
                    u_nick = user_id_to_nickname.get(v["user_id"], str(v["user_id"])[:8])
                    sel_name = dict_name_map.get(v["selected_candidate_id"], f"ID {v['selected_candidate_id']}")
                    print(f"     - 검증자: {u_nick:<3} | 선택: {sel_name:<12} | 응답시간: {v['response_time']:>5d}ms | 현재 평판 ρ: {float(v['trust_score'] or 0.2):.4f}")
                
                # 유저 신뢰도 맵
                user_trust_map = {v["user_id"]: float(v["trust_score"] if v["trust_score"] is not None else 0.2) for v in votes}
                
                # 베이지안 사후 확률 계산
                posteriors = calculate_bayesian_posterior(candidates, votes, user_trust_map)
                
                # 각 후보별 상세 데이터
                print("   " + "-"*130)
                print(f"   {'후보 생물종':<18} | {'AI 신뢰도':<10} | {'득표수(K)':<8} | {'합의율(K/N)':<10} | {'베이지안 사후확률':<15} | {'이항 p-value':<12} | {'확정 조건 만족도'}")
                print("   " + "-"*130)
                
                M = len(candidates)
                p0 = 1.0 / M
                
                for cand in candidates:
                    c_id = cand["id"]
                    c_name = dict_name_map.get(c_id, f"ID {c_id}")
                    ai_conf = float(cand["confidence_score"])
                    
                    K = sum(1 for v in votes if v["selected_candidate_id"] == c_id)
                    consensus_ratio = K / N if N > 0 else 0.0
                    post_prob = posteriors.get(c_id, 0.0)
                    p_val = calculate_binomial_p_value(N, K, p0)
                    
                    # 충족 조건 표시
                    if ai_conf < 0.1:
                        cond_desc = f"N>=5 ({'O' if N>=5 else 'X'}), p<0.01 ({'O' if p_val<0.01 else 'X'}), Post>=0.95 ({'O' if post_prob>=0.95 else 'X'})"
                        is_meet = N >= 5 and p_val < 0.01 and post_prob >= 0.95
                    else:
                        cond_desc = f"N>=3 ({'O' if N>=3 else 'X'}), p<0.05 ({'O' if p_val<0.05 else 'X'}), Post>=0.95 ({'O' if post_prob>=0.95 else 'X'})"
                        is_meet = N >= 3 and p_val < 0.05 and post_prob >= 0.95
                        
                    meet_status = "✅ 충족(확정)" if is_meet else "⏳ 미충족"
                    
                    print(f"   {c_name:<18} | {ai_conf:<10.2f} | {K:<8d} | {consensus_ratio:<10.2%} | {post_prob:<15.4%} | {p_val:<12.4f} | {cond_desc} -> {meet_status}")
                print("   " + "-"*130)
                
                # pictures 에서 현재 확정되었는지 조회
                cur.execute("SELECT confirmed_dictionary_id FROM pictures WHERE id = %s", (picture_id,))
                pic_confirmed = cur.fetchone()["confirmed_dictionary_id"]
                if pic_confirmed is not None:
                    confirmed_name = dict_name_map.get(pic_confirmed, f"ID {pic_confirmed}")
                    print(f"   🏆 [확정 결과] 최종 확정되었습니다! (확정 생물종: {confirmed_name})")
                else:
                    print(f"   ⏳ [확정 결과] 아직 확정 조건을 만족하지 못하여 검증 보류 중입니다.")
                    
    except Exception as e:
        print(f"⚠️ 중간 연산 분석 실패: {e}")


def simulate_user_minigame_vote(user_id, user_nickname, target_dictionary_id, response_time) -> bool:
    """실제 미니게임(pages/5_minigame.py)의 문제 조회 -> 선택지 생성 -> 제출 흐름을 백퍼센트 동일하게 모사(Simulation)합니다."""
    print(f"\n >>> {user_nickname} 유저 정답 투표 시뮬레이션 진입 중...")
    
    # 0. 평판제한 및 활동 차단 조건 검증 (실제 미니게임 로직 반영)
    # trust_score <= -0.2인 경우 참여 제한
    db_url = _db_url()
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT trust_score FROM users WHERE id = %s", (user_id,))
                user_row = cur.fetchone()
                if user_row and user_row["trust_score"] is not None and float(user_row["trust_score"]) <= -0.2:
                    print(f"⚠️ [{user_nickname}] 신뢰도 점수가 {float(user_row['trust_score']):.4f} <= -0.2 이므로 미니게임 검증 참여가 차단된 상태입니다. (실제 서비스 정책)")
                    return False
    except Exception as e:
        print(f"⚠️ [{user_nickname}] 유저 평판 검사 에러: {e}")
        return False

    # 1. 미니게임 문제 조회 (fetch_random_picture_for_minigame)
    pic = fetch_random_picture_for_minigame(user_id)
    if not pic:
        print(f"⚠️ [{user_nickname}] 문제를 가져오는 데 실패했습니다 (사진이 없거나 본인 업로드 사진 혹은 이미 참여함).")
        return False
        
    primary_id = pic["candidate_dictionary_id"]
    primary_name = pic["primary_name"]
    
    # 2. AI가 판별한 후보종들을 기본 선택지로 사용
    candidates = [{"id": c["id"], "name": c["name"]} for c in pic["candidates"]]
    
    # 3. 1순위 대표 후보(정답)가 후보 목록에 포함되어 있는지 확인 및 추가
    if not any(c["id"] == primary_id for c in candidates):
        candidates.append({"id": primary_id, "name": primary_name})
        
    # 4. 중복 제거
    candidate_ids = {c["id"] for c in candidates}
    
    # 5. 4개 미만인 경우 도감에서 랜덤하게 다른 종을 선택지로 채움 (중복 방지)
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT id, name FROM dictionary")
                dictionary_list = cur.fetchall()
    except Exception as e:
        print(f"⚠️ 도감 목록 쿼리 에러: {e}")
        return False

    if len(candidates) < 4:
        others = [d for d in dictionary_list if d["id"] not in candidate_ids]
        needed = 4 - len(candidates)
        wrong = random.sample(others, min(needed, len(others)))
        choices = candidates + [{"id": w["id"], "name": w["name"]} for w in wrong]
    else:
        choices = candidates[:4]
        
    # 셔플
    random.shuffle(choices)
    
    # 6. 생성된 4개 선택지 시각화 및 사용자 입력 대기
    print(f"   * 미니게임 출제 화면 렌더링 완료!")
    print(f"     - 캡차 제시 이미지 URL: {pic['storage_url']}")
    print(f"     - 시스템이 유도하는 AI 1순위 제시어 (primary_name): {primary_name}")
    print("\n   " + "-"*50)
    print(f"   [!] {user_nickname} 유저의 투표를 선택해 주세요.")
    print("       (원하는 번호를 입력하고 Enter를 누르세요. 그냥 Enter를 치면 자동 정답 제출)")
    print("   " + "-"*50)
    
    for idx, choice in enumerate(choices, 1):
        is_target = " [★ 정답]" if choice["id"] == target_dictionary_id else ""
        print(f"     [{idx}] {choice['name']} (ID: {choice['id']}){is_target}")
    print("   " + "-"*50)
    
    start_time = time.time()
    while True:
        try:
            user_input = input(f"   👉 {user_nickname} 선택 입력 (1~4, default=정답): ").strip()
            
            # 입력 시간 측정
            elapsed_time = int((time.time() - start_time) * 1000)
            if elapsed_time < 500:
                elapsed_time = 500
            
            if user_input == "":
                # 기본값: 정답 자동 선택
                selected_choice = next((c for c in choices if c["id"] == target_dictionary_id), choices[0])
                print(f"     (Enter 입력 ➡️ 정답 '{selected_choice['name']}' 자동 선택됨)")
                break
            else:
                idx_choice = int(user_input)
                if 1 <= idx_choice <= len(choices):
                    selected_choice = choices[idx_choice - 1]
                    break
                else:
                    print("     ⚠️ 1부터 4 사이의 번호를 입력해 주세요.")
        except ValueError:
            print("     ⚠️ 올바른 숫자를 입력해 주세요.")
            
    print(f"   * [{user_nickname}] 유저가 화면에서 '{selected_choice['name']}' 최종 선택 (소요시간: {elapsed_time}ms)")
    
    # 8. 최종 답안 등록 (record_picture_trust 호출)
    success = record_picture_trust(
        user_id=user_id,
        picture_id=pic["id"],
        selected_candidate_id=selected_choice["id"],
        response_time=elapsed_time
    )
    return success


def run_real_test():
    print("=" * 70)
    print("         EcoQuest 통계적 생물종 확정 모델 실동작 테스트 런타임         ")
    print("=" * 70)
    
    # 1. 이미지 경로 설정 (실행 인자가 있으면 사용, 없으면 기본값)
    default_img_path = "./docs/test/1.jpg"
    img_path = sys.argv[1] if len(sys.argv) > 1 else default_img_path
    img_path = os.path.abspath(img_path)
    
    if not os.path.exists(img_path):
        print(f"Error: 테스트 이미지 파일이 {img_path} 경로에 없습니다.")
        return
        
    print(f"🎯 테스트 대상 이미지: {img_path}")
    db_url = _db_url()
    test_user_ids = []
    picture_id = None
    storage_filename = None
    
    try:
        # 혹시 남아있을 수 있는 이전 테스트 찌꺼기 유저 데이터 사전 정리 (t1 ~ t30)
        u_nicknames = [f"t{i}" for i in range(1, 31)]
        prev_user_ids = []
        for nick in u_nicknames:
            u_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"ecoquest:{nick}")
            prev_user_ids.append(u_id)
            
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = ANY(%s)", (prev_user_ids,))
                conn.commit()
        print("[사전 테스트 찌꺼기 데이터 정리 완료 (t1 ~ t30)]")

        # 2. 이미지 실제 AI 분석 수행 및 에코퀘스트 도감 매칭
        print("\n[단계 2] Gemini Vision API 기반 실제 생물 분석 및 매칭...")
        try:
            matched_candidates = analyze_image_via_gemini(img_path)
            print(f" - 분석 및 매칭 성공 (총 {len(matched_candidates)}개 도감 후보 매칭됨):")
            for mc in matched_candidates:
                print(f"   * {mc['name']} (ID: {mc['id']}) - AI 신뢰도: {mc['confidence_score']:.2%}")
        except Exception as e:
            print(f"Error: 이미지 분석에 실패했습니다: {e}")
            return
            
        candidate_ids = [mc["id"] for mc in matched_candidates][:4]
        confidence_scores = [mc["confidence_score"] for mc in matched_candidates][:4]
        candidate_names = [mc["name"] for mc in matched_candidates][:4]
        
        target_candidate_id = candidate_ids[0]
        target_candidate_name = candidate_names[0]
            
        # 테스트 유저 가입 (t1)
        print("\n[단계 1] 테스트용 업로더 유저 가입 (t1)...")
        users = {}
        u_data = authenticate_user("t1")
        if not u_data:
            print("Error: 업로더 t1 가입 실패.")
            return
        users["t1"] = u_data
        test_user_ids.append(u_data["id"])
        print(f" - 업로더 't1' 가입 완료: UUID={u_data['id']} | 초기 평판 ρ={u_data['trust_score']:.2f}")

        # 3. 이미지 변환 및 압축 (실제 pages/1_home.py 의 구현 로직 적용)
        print("\n[단계 2.3] 테스트 이미지 압축 처리 (실제 서비스 구현 방식)...")
        compressed_io = compress_image(img_path)
        compressed_bytes = compressed_io.getvalue()
        print(f" - 압축 전 원본 크기: {os.path.getsize(img_path)/1024:.1f} KB ➡️ 압축 후 크기: {len(compressed_bytes)/1024:.1f} KB")

        # 4. 이미지 Supabase Storage에 업로드
        print("\n[단계 2.5] 테스트 이미지 Supabase Storage 업로드 실행...")
        storage_filename = f"real_test_{uuid.uuid4().hex[:8]}.jpg"
        public_url = upload_picture_to_supabase(compressed_bytes, storage_filename)
        print(f" - 업로드 성공! 반환된 Storage 경로/URL: {public_url}")
        
        # 5. 사진 업로드 트랜잭션 실행
        print("\n[단계 3] 사진 발견 및 AI 후보군 데이터 등록 트랜잭션 실행...")
        res_pic = insert_discovery_transaction(
            user_id=users["t1"]["id"],
            candidate_ids=candidate_ids,
            storage_url=public_url,
            confidence_scores=confidence_scores
        )
        if not res_pic or "duplicate" in res_pic:
            print("Error: 사진 발견 등록 실패.")
            return
            
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM pictures WHERE storage_url = %s", (public_url,))
                row = cur.fetchone()
                picture_id = row[0]
        print(f" - 사진 데이터 등록 완료! 생성된 picture_id = {picture_id}")
        
        # 6. 실시간 미니게임 투표 접수 및 연쇄 동작 모니터링 (확정될 때까지 무한 루프)
        print(f"\n[단계 4] 유저들이 실제 미니게임을 통해 사진이 확정(Confirmed)될 때까지 순차적으로 투표...")
        user_id_to_nickname = {u["id"]: nick for nick, u in users.items()}
        vote_index = 2
        
        while True:
            # DB에서 현재 확정 여부 확인
            confirmed_id = None
            with psycopg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT confirmed_dictionary_id FROM pictures WHERE id = %s", (picture_id,))
                    row = cur.fetchone()
                    if row:
                        confirmed_id = row[0]
            
            if confirmed_id is not None:
                break
                
            nick = f"t{vote_index}"
            print(f"\n ➡️ 신규 검증 참여 유저 '{nick}' 자동 등록 중...")
            u_data = authenticate_user(nick)
            if not u_data:
                print(f"Error: 유저 {nick} 가입 실패.")
                break
            
            users[nick] = u_data
            test_user_ids.append(u_data["id"])
            user_id_to_nickname[u_data["id"]] = nick
            print(f" - 유저 '{nick}' 가입 완료: UUID={u_data['id']} | 초기 평판 ρ={u_data['trust_score']:.2f}")
            
            # 투표 시뮬레이션 실행 (사용자에게 직접 입력을 받음)
            if simulate_user_minigame_vote(u_data["id"], nick, target_candidate_id, 1500):
                print_intermediate_status(picture_id, candidate_ids, candidate_names, user_id_to_nickname)
            else:
                print(f"⚠️ 유저 {nick}의 투표 진행 중 문제가 발생했습니다. 다음 유저로 진행합니다.")
                
            vote_index += 1
        
        print("\n" + "-"*50)
        print("          실시간 동작 상태 및 DB 쿼리 결과          ")
        print("-"*50)
        
        with psycopg.connect(db_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT confirmed_dictionary_id FROM pictures WHERE id = %s", (picture_id,))
                pic_row = cur.fetchone()
                confirmed_id = pic_row["confirmed_dictionary_id"]
                print(f" 1. 사진(ID: {picture_id})의 최종 확정 도감 ID: {confirmed_id} (기대값: {target_candidate_id})")
                
                print("\n 2. 검증 참여 유저 정보 변동 내역:")
                cur.execute(
                    "SELECT id, xp, trust_score FROM users WHERE id = ANY(%s)",
                    (test_user_ids,)
                )
                user_rows = {r["id"]: r for r in cur.fetchall()}
                
                for nick in sorted(users.keys()):
                    if nick == "t1":
                        continue
                    uid = users[nick]["id"]
                    if uid in user_rows:
                        curr_data = user_rows[uid]
                        print(f"   * 유저 {nick:3s}: XP = {curr_data['xp']} | 신뢰 계수 ρ = {curr_data['trust_score']:.4f}")
                
                u_id = users["t1"]["id"]
                uploader_data = user_rows[u_id]
                print(f"   * 업로더 t1: XP = {uploader_data['xp']} | 신뢰 계수 ρ = {uploader_data['trust_score']:.2f}")
 
    except Exception as e:
        print(f"\n⚠️ 테스트 중 오류 발생: {e}")
        
    finally:
        cleanup_real_test_data(test_user_ids, picture_id, storage_filename)
 
 
if __name__ == "__main__":
    run_real_test()
