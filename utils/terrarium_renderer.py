# -*- coding: utf-8 -*-

def map_animal_item(item_name: str) -> str:
    """아이템 명칭에 기반하여 동물 그래픽 유형(아키타입)을 매핑합니다."""
    if not item_name:
        return "none"
    
    item_name = item_name.strip()
    
    # 조류 매핑
    if any(k in item_name for k in ["새", "참새", "독수리", "까치", "까마귀", "비둘기", "닭", "꿩", "뻐꾸기", "갈매기"]):
        return "bird"
    
    # 포유류 중 토끼/설치류
    if any(k in item_name for k in ["토끼", "다람쥐", "청서", "쥐", "햄스터", "너구리"]):
        return "rabbit"
        
    # 포유류 중 사슴류
    if any(k in item_name for k in ["사슴", "고라니", "노루", "산양", "염소", "양", "말", "소"]):
        return "deer"
        
    # 곤충류
    if any(k in item_name for k in ["나비", "벌", "무당벌레", "잠자리", "매미", "메뚜기", "사마귀", "매듭풀"]):
        return "butterfly"
        
    # 파충류/양서류
    if any(k in item_name for k in ["도마뱀", "뱀", "개구리", "맹꽁이", "두꺼비"]):
        return "lizard"
        
    # 기본 폴백: 포유류는 보통 토끼 형상으로 귀엽게 렌더링
    return "rabbit"


def render_terrarium_svg(layout: list[dict]) -> str:
    """
    테라리움 슬롯 데이터를 기반으로 저폴리곤(Low-Poly) 스타일의 3D 2.5D 입체 SVG 코드를 생성합니다.
    """
    bg_item = None
    plant_item = None
    animal_item = None

    for slot in layout:
        cat_name = slot.get("slot_category_name")
        item_name = slot.get("equipped_item_name")
        if item_name:
            if cat_name == "배경":
                bg_item = item_name
            elif cat_name == "식물":
                plant_item = item_name
            elif cat_name == "동물":
                animal_item = item_name

    # 1. 배경 설정 (하늘)
    sky_svg = ""
    if bg_item == "별이 빛나는 밤하늘":
        sky_svg = """
        <!-- Starry Night Sky -->
        <polygon points="150,150 250,100 250,250" fill="#1e1b4b" />
        <polygon points="350,150 250,100 250,250" fill="#0f172a" />
        <polygon points="150,150 120,250 250,250" fill="#0f172a" />
        <polygon points="350,150 380,250 250,250" fill="#020617" />
        <polygon points="120,250 120,320 250,340 250,250" fill="#1e1b4b" />
        <polygon points="380,250 380,320 250,340 250,250" fill="#311042" />
        
        <!-- Crescent Moon -->
        <polygon points="290,130 305,120 312,132 297,140 288,132" fill="#fef08a" />
        
        <!-- Stars -->
        <polygon points="160,160 162,163 160,166 158,163" fill="#ffffff" />
        <polygon points="200,130 202,132 200,134 198,132" fill="#fef08a" />
        <polygon points="320,180 322,182 320,184 318,182" fill="#ffffff" />
        <polygon points="140,220 141,222 140,224 139,222" fill="#ffffff" />
        """
    elif bg_item == "노을빛 하늘":
        sky_svg = """
        <!-- Sunset Sky -->
        <polygon points="150,150 250,100 250,250" fill="#fef08a" />
        <polygon points="350,150 250,100 250,250" fill="#fde047" />
        <polygon points="150,150 120,250 250,250" fill="#fde047" />
        <polygon points="350,150 380,250 250,250" fill="#f97316" />
        <polygon points="120,250 120,320 250,340 250,250" fill="#ea580c" />
        <polygon points="380,250 380,320 250,340 250,250" fill="#f43f5e" />
        
        <!-- Sunset Clouds -->
        <polygon points="160,180 185,168 205,180 180,188" fill="rgba(254, 215, 170, 0.7)" />
        <polygon points="280,150 305,142 325,158 300,162" fill="rgba(244, 63, 94, 0.4)" />
        """
    else:
        # 기본 '밝은 하늘' 또는 디폴트
        sky_svg = """
        <!-- Bright Sky (Day) -->
        <polygon points="150,150 250,100 250,250" fill="#e0f2fe" />
        <polygon points="350,150 250,100 250,250" fill="#bae6fd" />
        <polygon points="150,150 120,250 250,250" fill="#bae6fd" />
        <polygon points="350,150 380,250 250,250" fill="#7dd3fc" />
        <polygon points="120,250 120,320 250,340 250,250" fill="#7dd3fc" />
        <polygon points="380,250 380,320 250,340 250,250" fill="#38bdf8" />
        
        <!-- Clouds -->
        <polygon points="160,180 185,168 205,180 180,188" fill="rgba(255, 255, 255, 0.8)" />
        <polygon points="280,150 305,142 325,158 300,162" fill="rgba(255, 255, 255, 0.8)" />
        """

    # 2. 바닥 흙 및 잔디 설정
    ground_svg = ""
    if plant_item:  # 식물/잔디가 배치된 경우 녹색 바닥 렌더링
        ground_svg = """
        <!-- Green Grass Ground -->
        <polygon points="250,340 120,320 250,370" fill="#40916c" />
        <polygon points="250,340 380,320 250,370" fill="#2d6a4f" />
        <polygon points="250,340 120,320 250,290" fill="#52b788" />
        <polygon points="250,340 380,320 250,290" fill="#1b4332" />
        
        <!-- Grass Tufts -->
        <!-- Tuft 1 -->
        <polygon points="175,330 180,315 183,330" fill="#74c69d" />
        <polygon points="180,330 185,310 188,330" fill="#52b788" />
        <polygon points="185,330 190,320 193,330" fill="#40916c" />
        <!-- Tuft 2 -->
        <polygon points="315,335 320,320 323,335" fill="#74c69d" />
        <polygon points="320,335 325,315 328,335" fill="#52b788" />
        <!-- Tuft 3 -->
        <polygon points="225,355 230,340 233,355" fill="#52b788" />
        <polygon points="228,355 234,335 238,355" fill="#40916c" />
        """
    else:  # 비어있는 경우 황갈색 흙 바닥
        ground_svg = """
        <!-- Soil Ground -->
        <polygon points="250,340 120,320 250,370" fill="#8b5a2b" />
        <polygon points="250,340 380,320 250,370" fill="#734d26" />
        <polygon points="250,340 120,320 250,290" fill="#66401a" />
        <polygon points="250,340 380,320 250,290" fill="#59330e" />
        """

    # 바닥 흙 측면 단면 (언제나 갈색 3D 입체감 표현)
    base_sides_svg = """
    <!-- Soil Section Sides -->
    <polygon points="120,320 250,370 250,440 120,390" fill="#5c4033" />
    <polygon points="380,320 250,370 250,440 380,390" fill="#4b3621" />
    """

    # 3. 식물 렌더링
    plant_svg = ""
    if plant_item:
        if "선인장" in plant_item:
            plant_svg = """
            <!-- Cactus Model -->
            <!-- Main Trunk -->
            <polygon points="245,340 245,280 252,275 252,342" fill="#40916c" />
            <polygon points="252,342 252,275 258,280 258,340" fill="#2d6a4f" />
            
            <!-- Left Arm -->
            <polygon points="240,315 240,305 245,307 245,317" fill="#52b788" />
            <polygon points="235,305 235,285 240,288 240,307" fill="#40916c" />
            
            <!-- Right Arm -->
            <polygon points="258,300 258,292 263,294 263,302" fill="#2d6a4f" />
            <polygon points="263,294 263,278 267,280 267,296" fill="#52b788" />
            
            <!-- Flowers -->
            <polygon points="248,276 252,270 256,276 252,280" fill="#ff0a54" />
            <polygon points="234,286 237,282 240,286 237,289" fill="#ff477e" />
            """
        elif "단풍나무" in plant_item:
            plant_svg = """
            <!-- Maple Tree Model -->
            <!-- Trunk -->
            <polygon points="245,340 247,260 251,260 251,342" fill="#5c4033" />
            <polygon points="251,342 251,260 255,260 257,340" fill="#4b3621" />
            
            <!-- Low-poly Leaf Canopy -->
            <polygon points="220,260 250,210 265,255" fill="#d90429" />
            <polygon points="240,260 270,205 285,250" fill="#ef233c" />
            <polygon points="230,230 250,180 275,225" fill="#f77f00" />
            <polygon points="215,245 235,200 255,240" fill="#fcbf49" />
            <polygon points="245,215 260,175 275,210" fill="#ffb703" />
            <polygon points="235,260 250,245 260,260" fill="#6a040f" />
            """
        else:
            # 기타 식물 또는 기본 잔디 이외의 식물: 일반 나무 형태
            plant_svg = """
            <!-- Generic Low-poly Tree -->
            <!-- Trunk -->
            <polygon points="246,340 248,270 252,270 254,340" fill="#5c4033" />
            
            <!-- Green Canopy -->
            <polygon points="225,270 250,220 275,270" fill="#2d6a4f" />
            <polygon points="235,240 250,190 265,240" fill="#40916c" />
            <polygon points="240,210 250,170 260,210" fill="#52b788" />
            """

    # 4. 동물 렌더링
    animal_svg = ""
    if animal_item:
        mapped_type = map_animal_item(animal_item)
        
        if mapped_type == "rabbit":
            animal_svg = """
            <!-- Rabbit Model -->
            <g transform="translate(10, 5)">
                <!-- Body back -->
                <polygon points="190,340 180,330 190,320 200,330" fill="#f1f3f5" />
                <!-- Body front -->
                <polygon points="200,330 190,320 200,315 210,325 210,340" fill="#ffffff" />
                <!-- Head -->
                <polygon points="210,325 200,315 208,305 215,315" fill="#e9ecef" />
                <!-- Ear Left -->
                <polygon points="203,308 200,290 206,305" fill="#ffffff" />
                <polygon points="202,305 201,293 204,302" fill="#ffccd5" />
                <!-- Ear Right -->
                <polygon points="208,305 212,288 212,305" fill="#e9ecef" />
                <polygon points="209,302 211,291 211,302" fill="#ffccd5" />
                <!-- Tail -->
                <polygon points="180,330 176,327 178,333" fill="#ffffff" />
            </g>
            """
        elif mapped_type == "bird":
            animal_svg = """
            <!-- Bird Model -->
            <g transform="translate(-10, -5)">
                <!-- Body back -->
                <polygon points="280,325 295,305 285,300" fill="#3f37c9" />
                <!-- Body front -->
                <polygon points="285,300 295,305 305,295 295,290" fill="#4895ef" />
                <!-- Belly -->
                <polygon points="280,325 295,305 295,320" fill="#ffee55" />
                <!-- Head -->
                <polygon points="295,290 305,295 308,285 298,280" fill="#4cc9f0" />
                <!-- Beak -->
                <polygon points="308,285 315,288 305,292" fill="#f77f00" />
                <!-- Wing -->
                <polygon points="282,310 295,305 290,318" fill="#4361ee" />
                <!-- Tail -->
                <polygon points="272,335 280,325 277,322" fill="#3f37c9" />
            </g>
            """
        elif mapped_type == "deer":
            animal_svg = """
            <!-- Deer Model -->
            <g transform="translate(-15, -10)">
                <!-- Legs -->
                <polygon points="272,335 274,335 274,315 272,315" fill="#8b5a2b" />
                <polygon points="276,335 278,335 278,315 276,315" fill="#734d26" />
                <polygon points="292,335 294,335 294,315 292,315" fill="#8b5a2b" />
                <polygon points="296,335 298,335 298,315 296,315" fill="#734d26" />
                <!-- Body -->
                <polygon points="270,315 270,300 290,295 300,315" fill="#d2b48c" />
                <polygon points="270,300 290,295 300,310 300,315" fill="#c68642" />
                <!-- Neck -->
                <polygon points="290,295 300,310 302,280 292,285" fill="#b58253" />
                <!-- Head -->
                <polygon points="292,285 302,280 308,272 300,270" fill="#d2b48c" />
                <!-- Snout -->
                <polygon points="308,272 312,275 305,278" fill="#4b3621" />
                <!-- Antlers -->
                <polygon points="298,270 294,260 297,262 299,268" fill="#f5ebe0" />
                <polygon points="300,270 304,258 307,260 302,268" fill="#f5ebe0" />
            </g>
            """
        elif mapped_type == "butterfly":
            animal_svg = """
            <!-- Butterfly Model -->
            <g>
                <!-- Butterfly 1 -->
                <polygon points="210,230 200,220 205,215" fill="#ffb703" />
                <polygon points="210,230 220,220 215,215" fill="#fb8500" />
                <line x1="210" y1="230" x2="210" y2="220" stroke="#020617" stroke-width="1.5" />
                
                <!-- Butterfly 2 -->
                <polygon points="280,200 272,192 276,188" fill="#ffccd5" />
                <polygon points="280,200 288,192 284,188" fill="#ff477e" />
                <line x1="280" y1="200" x2="280" y2="192" stroke="#020617" stroke-width="1.5" />
            </g>
            """
        elif mapped_type == "lizard":
            animal_svg = """
            <!-- Lizard Model -->
            <g transform="translate(10, 0)">
                <!-- Body back / tail -->
                <polygon points="200,362 215,358 220,358" fill="#38b000" />
                <!-- Body front -->
                <polygon points="220,358 235,355 240,358 230,363" fill="#70e000" />
                <!-- Head -->
                <polygon points="235,355 240,358 245,354 240,350" fill="#9df020" />
                <!-- Legs -->
                <polygon points="212,358 215,360 212,363" fill="#38b000" />
                <polygon points="232,356 235,358 232,361" fill="#38b000" />
            </g>
            """

    # 5. 유리구 통 (돔 및 앞면 반사광)
    glass_svg = """
    <!-- Glass Dome Inside Glow/Refraction back -->
    <polygon points="150,150 350,150 380,250 380,320 250,340 120,320 120,250" fill="rgba(255, 255, 255, 0.02)" stroke="rgba(255,255,255,0.08)" stroke-width="1" />
    """

    # 유리 돔 앞면 덮개 및 광택 하이라이트 (바닥, 식물, 동물 위에 그림)
    glass_front_svg = """
    <!-- Glass Stopper (Neck & Cork) -->
    <polygon points="220,100 280,100 280,110 220,110" fill="rgba(255, 255, 255, 0.2)" stroke="rgba(255, 255, 255, 0.4)" stroke-width="1" />
    <polygon points="225,100 275,100 270,80 230,80" fill="#a0522d" />
    <polygon points="225,100 275,100 273,90 227,90" fill="#8b5a2b" />
    
    <!-- Glass Jar Front Facets -->
    <polygon points="150,150 250,100 250,230 150,200" fill="rgba(255, 255, 255, 0.03)" stroke="rgba(255,255,255,0.12)" stroke-width="1" />
    <polygon points="350,150 250,100 250,230 350,200" fill="rgba(255, 255, 255, 0.01)" stroke="rgba(255,255,255,0.12)" stroke-width="1" />
    <polygon points="150,200 250,230 250,370 120,320" fill="rgba(255, 255, 255, 0.03)" stroke="rgba(255,255,255,0.15)" stroke-width="1.2" />
    <polygon points="350,200 250,230 250,370 380,320" fill="rgba(255, 255, 255, 0.04)" stroke="rgba(255,255,255,0.15)" stroke-width="1.2" />
    <polygon points="120,320 250,370 380,320 380,390 250,440 120,390" fill="rgba(255, 255, 255, 0.01)" stroke="rgba(255,255,255,0.2)" stroke-width="1.5" />
    
    <!-- Shiny Reflections -->
    <polygon points="170,180 182,175 163,310 151,312" fill="rgba(255, 255, 255, 0.12)" />
    <polygon points="330,180 338,178 355,300 347,302" fill="rgba(255, 255, 255, 0.06)" />
    """

    # 전체 SVG 조립 및 CSS 부유(floating) 애니메이션 주입
    svg_code = f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="118 78 264 366" width="100%" height="100%" style="overflow: visible;">
        <style>
            @keyframes float {{
                0% {{ transform: translateY(0px); }}
                50% {{ transform: translateY(-10px); }}
                100% {{ transform: translateY(0px); }}
            }}
            .lowpoly-terrarium-container {{
                animation: float 5s ease-in-out infinite;
                transform-origin: center;
            }}
            /* 호버 시 디테일 쉐도우 효과 */
            polygon {{
                transition: fill 0.3s ease;
            }}
        </style>
        <g class="lowpoly-terrarium-container">
            {glass_svg}
            {sky_svg}
            {base_sides_svg}
            {ground_svg}
            {plant_svg}
            {animal_svg}
            {glass_front_svg}
        </g>
    </svg>
    """
    return svg_code
