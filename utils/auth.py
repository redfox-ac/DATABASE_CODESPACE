import random
import io
import time
import uuid
import streamlit as st
from google import genai
from google.genai import errors
from PIL import Image
from pydantic import BaseModel, Field

from utils.vworld import get_administrative_district
from utils.image import get_gps
from utils.db import (
    fetch_user,
    fetch_all_dictionary,
    insert_discovery_transaction,
    upload_picture_to_supabase,
)

# AI Models & helpers for Lens
class SpeciesCandidate(BaseModel):
    name: str = Field(description="동물의 한국어 생물종 이름")
    confidence_score: float = Field(description="이 분석 결과에 대한 AI의 확신 점수 (0.0-1.0 사이)")

class ImageAnalysisResult(BaseModel):
    candidates: list[SpeciesCandidate] = Field(
        description="분석 결과로 추정되는 생물종 후보 목록. 이미지의 생물이 확실하더라도 추후 검증을 위해 반드시 유사종이나 가능성이 있는 후보종들을 포함하여 최소 2개, 최대 4개까지 신뢰도가 높은 순으로 제공해야 합니다."
    )

def compress_image(uploaded_file, max_size_bytes=2 * 1024 * 1024) -> io.BytesIO:
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

def analyze_image_via_gemini(img_source, source_name: str = "image.jpg"):
    if "GEMINI_API_KEY" not in st.secrets:
        raise ValueError("GEMINI_API_KEY가 st.secrets에 설정되지 않았습니다.")
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    config = genai.types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ImageAnalysisResult,
        temperature=0.1
    )
    if isinstance(img_source, str):
        with open(img_source, "rb") as f:
            img_bytes = f.read()
    else:
        img_bytes = img_source
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            Image.open(io.BytesIO(img_bytes)), 
            "이 이미지를 정밀하게 분석해서 지정된 형식의 JSON 데이터로 출력해줘. 이미지가 아주 확실하더라도, 나중의 검증을 위해 형태적으로 가장 유사하거나 가능성이 있는 구체적인 한국어 생물종 후보를 포함하여 **최대 4개**의 후보 목록(candidates)을 항상 채워서 반환해줘. 포괄적인 분류명(예: 벌, 도마뱀)보다는 구체적인 한국어 국명(예: 쌍살벌, 장수도마뱀)을 우선적으로 사용해줘."
        ],
        config=config,
    )
    return response

@st.dialog("📸 생물 수집 렌즈")
def collection_lens():
    user = st.session_state.user_info
    st.markdown("촬영한 생물 사진을 업로드해 주세요.")
    uploaded = st.file_uploader(
        "이미지 선택",
        type=["jpg", "jpeg", "png", "webp"],
        key="collection_upload",
    )
    if uploaded is None:
        return

    pos = get_gps(uploaded)
    if pos is None:
        st.error("사진에서 위치 정보를 찾을 수 없습니다.")
        return
    
    lat, lon = pos
    address_data = get_administrative_district(lat, lon)
    if address_data is None:
        st.error("해당 위치에 대한 정보를 찾을 수 없습니다.")
        return
    if address_data:
        st.warning("⚠️ 보호 구역에서 촬영된 사진입니다. 사진이 도감에 반영되지 않습니다")
        return

    with st.status("분석 중...", expanded=True) as status:
        try:
            status.update(label="이미지 변환 및 압축 중...")
            compressed_io = compress_image(uploaded)
            compressed_bytes = compressed_io.getvalue()
            
            status.update(label="사진 분석 중...")
            response = analyze_image_via_gemini(compressed_bytes, uploaded.name)
            
            candidates = response.parsed.candidates if response.parsed else []
            if not candidates:
                status.update(label="분석 실패", state="error")
                st.error("❌ 이미지에서 식별된 생물종 후보가 없습니다.")
                return

            dict_list = fetch_all_dictionary()
            matched_candidates = []
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
                status.update(label="분석 실패", state="error")
                st.error(f"❌ 분석된 생물종 후보들({[c.name for c in candidates]})이 에코퀘스트의 생물 목록에 등록되어 있지 않습니다.")
                return

            matched_candidates.sort(key=lambda x: x["confidence_score"], reverse=True)
            primary_candidate = matched_candidates[0]
            species_name = primary_candidate["name"]
            
            candidate_ids = [c["id"] for c in matched_candidates]
            confidence_scores = [c["confidence_score"] for c in matched_candidates]
            
            if len(candidate_ids) < 4:
                others = [d for d in dict_list if d["id"] not in candidate_ids]
                needed = 4 - len(candidate_ids)
                wrong = random.sample(others, min(needed, len(others)))
                for w in wrong:
                    candidate_ids.append(w["id"])
                    confidence_scores.append(0.01)
                    
            candidate_ids = candidate_ids[:4]
            confidence_scores = confidence_scores[:4]
            
            status.update(label="이미지 업로드 중...")
            file_name = f"{user['id']}_{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
            public_url = upload_picture_to_supabase(compressed_bytes, file_name)
            
            status.update(label="데이터 저장 중...")
            result = insert_discovery_transaction(
                user_id=user["id"],
                candidate_ids=candidate_ids,
                storage_url=public_url,
                confidence_scores=confidence_scores
            )
            
            if result is None:
                status.update(label="저장 실패", state="error")
                st.error("생물 수집 데이터를 저장하는 데 실패했습니다.")
                return
                
            status.update(label="분석 완료 및 저장 완료!", state="complete", expanded=False)
            
        except errors.ServerError as e:
            status.update(label="분석 실패", state="error")
            st.error("현재 이용량이 많아 요청을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.")
            return
        except Exception as e:
            status.update(label="분석 중 오류 발생", state="error")
            st.error(f"분석 중 오류가 발생했습니다: {e}")
            return
            
    if result.get("duplicate"):
        st.warning(f"이미 수집한 생물입니다: **{species_name}**")
        return
        
    if result.get("is_protected"):
        st.warning(
            f"⚠️ **{species_name}** — 법정 보호종으로 확인되었습니다. 관찰 기록만 저장되며, 채집·포획은 금지됩니다. (+10 XP)"
        )
    else:
        st.success(f"🎉 **{species_name}** 수집 완료! (+10 XP)")

    st.markdown("##### 🤖 AI가 분석한 생물종 후보 목록:")
    for mc in matched_candidates:
        st.markdown(f"- **{mc['name']}** (신뢰도: {mc['confidence_score'] * 100:.1f}%)")

    # 세션 갱신
    updated = fetch_user(user["id"], nickname=user.get("nickname", ""))
    if updated:
        st.session_state.user_info = updated
    st.rerun()

def init_session() -> None:
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user_info" not in st.session_state:
        st.session_state.user_info = None

def render_sidebar_nav() -> None:
    """로그인 상태에서 모든 페이지에 동일한 좌측 메뉴를 표시합니다."""
    user = st.session_state.user_info
    
    # 세션 최신화 (실시간 XP/레벨을 사이드바에 렌더링하기 위해)
    fresh = fetch_user(user["id"], nickname=user.get("nickname", ""))
    if fresh:
        st.session_state.user_info = fresh
        user = fresh

    xp = user.get("xp", 0)
    max_xp = user.get("max_xp", 200) or 200
    progress = min(xp / max_xp, 1.0) if max_xp > 0 else 0.0

    with st.sidebar:
        st.markdown("### 🌿 EcoQuest")
        
        # 유저 정보 (닉네임, 경험치 및 진행도) 사이드바 상단 배치
        st.markdown(f"👤 **{user['nickname']}**")
        st.progress(progress, text=f"경험치 {xp} / {max_xp} XP")
        
        # 생물 수집 렌즈 버튼 바로 아래 배치
        st.markdown("<div style='margin-top: 4px;'></div>", unsafe_allow_html=True)
        if st.button("📸 생물 수집 렌즈", type="primary", use_container_width=True):
            collection_lens()
            
        st.divider()
        st.page_link("app.py", label="홈", icon="🏠")
        st.page_link("pages/2_dictionary.py", label="도감", icon="📖")
        st.page_link("pages/3_quest.py", label="퀘스트", icon="🎯")
        st.page_link("pages/4_terrarium.py", label="테라리움", icon="🪴")
        st.divider()
        if st.button("로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_info = None
            st.switch_page("app.py")

def require_login() -> None:
    """미로그인 차단 + 로그인 시 사이드바 메뉴 유지."""
    init_session()
    if not st.session_state.get("logged_in") or not st.session_state.get("user_info"):
        st.warning("로그인이 필요합니다. 메인 화면에서 닉네임으로 로그인해 주세요.")
        st.page_link("app.py", label="로그인하러 가기", icon="🔐")
        st.stop()
    render_sidebar_nav()
