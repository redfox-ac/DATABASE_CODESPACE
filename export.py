import argparse
import sys
import os
import csv
import datetime
import psycopg
from psycopg.rows import dict_row

# Streamlit secrets 로드를 위한 모의 환경 셋업 및 패스 지정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# utils/db.py 에서 DB URL 및 통계 알고리즘 임포트
from utils.db import (
    _db_url,
    calculate_bayesian_posterior,
    calculate_binomial_p_value,
)

def parse_args():
    parser = argparse.ArgumentParser(
        description="연구용 생물 관찰 데이터 및 GPS 위치 정보 가공 추출 도구"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./exported_biodiversity_data.csv",
        help="출력할 CSV 파일 경로 (기본값: ./exported_biodiversity_data.csv)"
    )
    parser.add_argument(
        "--confirmed-only",
        action="store_true",
        default=False,
        help="검증 완료(확정)된 관찰 데이터만 추출할지 여부"
    )
    parser.add_argument(
        "--category", "-c",
        type=str,
        default=None,
        help="특정 생물 분류 카테고리 필터링 (예: 조류, 곤충류)"
    )
    parser.add_argument(
        "--protected-only",
        action="store_true",
        default=False,
        help="법정 보호종 데이터만 추출할지 여부"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="조회 시작일 (YYYY-MM-DD 형식, 예: 2026-06-01)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="조회 종료일 (YYYY-MM-DD 형식, 예: 2026-06-30)"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    db_url = _db_url()
    
    print("=" * 70)
    print("      EcoQuest 생물 위치 정보 데이터 추출 도구 (Research Export)      ")
    print("=" * 70)
    
    # SQL 쿼리 조건 동적 결합
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
    
    if args.confirmed_only:
        conditions.append("p.confirmed_dictionary_id IS NOT NULL")
        
    if args.protected_only:
        conditions.append("d.is_protected = TRUE")
        
    if args.category:
        conditions.append("dc.name = %s")
        params.append(args.category)
        
    if args.start_date:
        try:
            start_dt = datetime.datetime.strptime(args.start_date, "%Y-%m-%d")
            conditions.append("p.created_at >= %s")
            params.append(start_dt)
        except ValueError:
            print(f"❌ 에러: 시작일 형식(--start-date)이 올바르지 않습니다. (YYYY-MM-DD 필요)")
            sys.exit(1)
            
    if args.end_date:
        try:
            # 해당 일자의 23시 59분 59초까지 포함되도록 처리
            end_dt = datetime.datetime.strptime(args.end_date, "%Y-%m-%d") + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
            conditions.append("p.created_at <= %s")
            params.append(end_dt)
        except ValueError:
            print(f"❌ 에러: 종료일 형식(--end-date)이 올바르지 않습니다. (YYYY-MM-DD 필요)")
            sys.exit(1)
            
    if conditions:
        query_base += " AND " + " AND ".join(conditions)
        
    query_base += " ORDER BY p.id ASC"
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                print("⚡ 관찰 데이터 조회 중...")
                cur.execute(query_base, params)
                records = cur.fetchall()
                
                total_records = len(records)
                print(f"📊 총 {total_records}개의 관찰 레코드를 필터링했습니다.")
                
                exported_data = []
                
                for idx, row in enumerate(records, 1):
                    pic_id = row["observation_id"]
                    matched_dict_id = row["matched_dictionary_id"]
                    
                    # 1. AI 후보군(candidates) 조회
                    cur.execute(
                        "SELECT dictionary_id AS id, confidence_score FROM picture_candidates WHERE picture_id = %s",
                        (pic_id,)
                    )
                    candidates_rows = cur.fetchall()
                    
                    # 2. 미니게임 투표 정보 조회 (response_time 범위 필터링 적용)
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
                    
                    # 통계 인자 변환
                    candidates = [{"id": r["id"], "confidence_score": float(r["confidence_score"])} for r in candidates_rows]
                    votes = [{"user_id": r["user_id"], "selected_candidate_id": r["selected_candidate_id"]} for r in votes_rows]
                    user_trust_map = {r["user_id"]: float(r["trust_score"]) for r in votes_rows}
                    
                    # 수학적 신뢰도 통계량 계산
                    n = len(votes)
                    k = sum(1 for v in votes if v["selected_candidate_id"] == matched_dict_id)
                    M = len(candidates)
                    p0 = 1.0 / M if M > 0 else 0.25
                    
                    if M == 0:
                        confidence = 0.0
                        p_val = 1.0
                    else:
                        posteriors = calculate_bayesian_posterior(candidates, votes, user_trust_map)
                        # 투표가 없으면 AI 점수로 폴백
                        if n == 0:
                            confidence = next((float(c["confidence_score"]) for c in candidates if c["id"] == matched_dict_id), 0.0)
                            p_val = 1.0
                        else:
                            confidence = posteriors.get(matched_dict_id, 0.0)
                            p_val = calculate_binomial_p_value(n, k, p0)
                            
                    # 관찰 시각 로컬 문자열 변환
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
                    
                    if idx % 10 == 0 or idx == total_records:
                        print(f" ⚙️ 통계 가공 처리 중... ({idx}/{total_records})")
                
                # CSV 출력
                output_path = os.path.abspath(args.output)
                output_dir = os.path.dirname(output_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                    
                headers = [
                    "observation_id", "species_name", "category_name", "is_protected",
                    "latitude", "longitude", "is_confirmed", "confidence", "p_value",
                    "vote_count", "observed_at"
                ]
                
                with open(output_path, "w", encoding="utf-8-sig", newline="") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(exported_data)
                    
                print("=" * 70)
                print(f"🎉 파일 내보내기 성공! 경로: {output_path}")
                print("=" * 70)
                
    except Exception as e:
        print(f"❌ 데이터베이스 처리 중 오류가 발생했습니다: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
