# pyrefly: ignore [untyped-import]
import requests
import streamlit as st

def get_administrative_district(lat, lon):

    if not lat or not lon:
        return None
    
    api_key = st.secrets["VWORLD_API_KEY"]
    proxy_token = st.secrets["PROXY_TOKEN"]
    
    # 해외 IP 접속 불가능으로 인한 홈서버 프록시
    # url = "https://api.vworld.kr/req/data"
    url = "https://morae.parrot-luma.ts.net/proxy/vworld" 

    service_domain = "https://github.com/redfox-ac/DATABASE_CODESPACE"
    
    params = {
        "service": "data",
        "request": "GetFeature",
        "data": "LT_C_UM221",
        "key": api_key,
        "geomFilter": f"POINT({lon} {lat})",
        "attrFilter": "uname:like:야생동·식물보호구역",
        "crs": "EPSG:4326",
        "domain": service_domain,
        "size": "1",
        "token": proxy_token,
    }
    
    # 3. API 요청
    try:
        response = requests.get(url, params=params, timeout=5)

        if response.status_code != 200:
            return None

        res_data = response.json()
        status = res_data.get("response", {}).get("status")

        if status == "OK":
            features = (
                res_data.get("response", {})
                .get("result", {})
                .get("featureCollection", {})
                .get("features", [])
            )
            
            return len(features) > 0

        elif status == "NOT_FOUND":
            return False

        else:
            return None

    except Exception:
        return None