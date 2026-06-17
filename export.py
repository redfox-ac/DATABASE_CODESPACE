import argparse
import sys
import os
import csv
import datetime
import psycopg
from psycopg.rows import dict_row

# Streamlit secrets 로드를 위한 모의 환경 셋업 및 패스 지정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# utils/db.py 에서 데이터 추출 함수 임포트
from utils.db import fetch_research_data

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
    
    print("=" * 70)
    print("      EcoQuest 생물 위치 정보 데이터 추출 도구 (Research Export)      ")
    print("=" * 70)
    
    try:
        print("⚡ 관찰 데이터 조회 및 가공 중...")
        exported_data = fetch_research_data(
            confirmed_only=args.confirmed_only,
            category=args.category,
            protected_only=args.protected_only,
            start_date=args.start_date,
            end_date=args.end_date
        )
        
        total_records = len(exported_data)
        print(f"📊 총 {total_records}개의 관찰 레코드를 필터링했습니다.")
        
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
