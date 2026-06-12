# 에코퀘스트 데이터베이스 설계 및 구축

---

## DB 스키마 정의

### 테이블 설명

#### 기준 정보

- **ItemsCategory**: 아이템 카테고리 정의

| **필드명**    | **설명**                     |
| ------------- | ---------------------------- |
| `id`          | 아이템 분류 고유 번호        |
| `name`        | 분류 명칭 (예: '돌', '배경') |
| `description` | 카테고리에 대한 부가 설명    |

- **Items**: 아이템 종류 정의

| **필드명**    | **설명**            |
| ------------- | ------------------- |
| `id`          | 아이템 고유 번호    |
| `name`        | 아이템 명칭         |
| `category_id` | 소속 아이템 분류 ID |

- **DictionaryCategories**: 생물 분류 정의

| **필드명**    | **설명**                    |
| ------------- | --------------------------- |
| `id`          | 생물 분류 고유 번호         |
| `name`        | 분류 명칭 ('새', '나무' 등) |
| `description` | 분류 설명                   |

- **Dictionary**: 생물종 정의

| **필드명**     | **설명**                      |
| -------------- | ----------------------------- |
| `id`           | 생물 도감 고유 번호           |
| `name`         | 생물의 명칭                   |
| `description`  | 생물의 설명                   |
| `is_protected` | 법정 보호종 여부 (TRUE/FALSE) |
| `category_id`  | 소속 생물 분류 ID             |

- **TerrariumSlot**: 테라리움의 아이템 장착이 가능한 슬롯 정의

| **필드명**    | **설명**                                   |
| ------------- | ------------------------------------------ |
| `id`          | 슬롯 고유 번호                             |
| `name`        | 슬롯 표현 이름 (예: '돌 슬롯 1')           |
| `description` | 슬롯 설명                                  |
| `category_id` | 해당 슬롯에 장착 가능한 아이템 카테고리 ID |

#### 유저 & 인벤토리

- **Users**: 사용자 데이터

| **필드명**    | **설명**                                  |
| ------------- | ----------------------------------------- |
| `id`          | 유저 고유 ID (Supabase Auth 연동 UUID)    |
| `xp`          | 유저의 누적 경험치 (레벨 산출용)          |
| `trust_score` | 미니게임 응답에 따라 변동되는 신뢰도 점수 |
| `created_at`  | 계정 생성 일시                            |

- **UserInventory**: 사용자별 가지는 아이템 데이터

| **필드명**    | **설명**                  |
| ------------- | ------------------------- |
| `id`          | 인벤토리 개별 고유 번호   |
| `user_id`     | 인벤토리의 주인 (유저 ID) |
| `item_id`     | 획득한 아이템 마스터 ID   |
| `quantity`    | 해당 아이템의 보유 수량   |
| `acquired_at` | 아이템을 획득한 일시      |

- **UserTerrarium**: 사용자별 개인 테라리움의 슬롯에 장착한 아이템 정보

| **필드명** | **설명**                                              |
| ---------- | ----------------------------------------------------- |
| `user_id`  | 테라리움을 소유한 유저 ID                             |
| `slot_id`  | 장착된 테라리움 슬롯 ID                               |
| `item_id`  | 슬롯에 장착된 아이템 마스터 ID (인벤토리 소유 검증용) |

#### 퀘스트

- **Quest**: 퀘스트 데이터

| **필드명**    | **설명**                 |
| ------------- | ------------------------ |
| `id`          | 퀘스트 마스터 고유 번호  |
| `description` | 퀘스트 내용 및 설명      |
| `reward_xp`   | 보상으로 주어지는 경험치 |
| `expire_at`   | 퀘스트 만료 일시         |

- **QuestReward**: 퀘스트 보상 정보

| **필드명** | **설명**                    |
| ---------- | --------------------------- |
| `quest_id` | 연결된 퀘스트 ID            |
| `item_id`  | 보상으로 주어지는 아이템 ID |
| `amount`   | 지급되는 아이템의 수량      |

- **TargetDictionary**: 퀘스트 목표 (생물종)

| **필드명**      | **설명**                          |
| --------------- | --------------------------------- |
| `quest_id`      | 연결된 퀘스트 ID                  |
| `dictionary_id` | 퀘스트의 목표 생물 도감 ID        |
| `target_count`  | 해당 생물 달성에 필요한 수행 횟수 |

- **TargetDictionaryCategories**: 퀘스트 목표 (생물 분류)

| **필드명**     | **설명**                               |
| -------------- | -------------------------------------- |
| `quest_id`     | 연결된 퀘스트 ID                       |
| `category_id`  | 퀘스트의 목표 생물 분류 ID             |
| `target_count` | 해당 생물 분류 달성에 필요한 수행 횟수 |

- **UserQuest**: 유저의 퀘스트 진행 정보

| **필드명** | **설명**                                          |
| ---------- | ------------------------------------------------- |
| `user_id`  | 퀘스트를 수행하는 유저 ID                         |
| `quest_id` | 수행 중인 퀘스트 마스터 ID                        |
| `status`   | 진행 상태 ('in_progress', 'completed', 'expired') |

- **QuestProgressDictionary**: 유저의 퀘스트 상세 진행 정보 (생물종)

| **필드명**      | **설명**                           |
| --------------- | ---------------------------------- |
| `user_id`       | 퀘스트 수행 유저 ID                |
| `quest_id`      | 대상 퀘스트 ID                     |
| `dictionary_id` | 추적 중인 목표 생물 도감 ID        |
| `current_count` | 현재까지 유저가 촬영에 성공한 횟수 |

- **QuestProgressDictionaryCategories**: 유저의 퀘스트 상세 진행 정보 (생물 분류)

| 필드명          | **설명**                           |
| --------------- | ---------------------------------- |
| `user_id`       | 퀘스트 수행 유저 ID                |
| `quest_id`      | 대상 퀘스트 ID                     |
| `category_id`   | 추적 중인 목표 생물 분류 ID        |
| `current_count` | 현재까지 유저가 촬영에 성공한 횟수 |

#### 이미지 및 검증

- **Pictures**: 사진 데이터

| **필드명**                | **설명**                                                              |
| ------------------------- | --------------------------------------------------------------------- |
| `id`                      | 사진 고유 번호                                                        |
| `user_id`                 | 사진을 업로드한 유저 ID                                               |
| `storage_url`             | Supabase Storage 이미지 경로                                          |
| `latitude`                | 촬영 위도                                                             |
| `longitude`               | 촬영 경도                                                             |
| `candidate_dictionary_id` | AI가 1차로 추정한 생물 도감 고유 번호 (도감에 매칭된 1순위 대표 후보) |
| `confirmed_dictionary_id` | 미니게임 다수결을 통해 최종 확정된 생물종 ID                          |

- **PictureCandidates**: 사진 후보 생물종 목록

| **필드명**         | **설명**                      |
| ------------------ | ----------------------------- |
| `picture_id`       | 대상 사진 ID                  |
| `dictionary_id`    | AI가 추정한 후보 생물종 ID    |
| `confidence_score` | AI의 확신 점수 (0.0-1.0 사이) |

- **PictureTrust**: 유저가 등록한 사진 신뢰 정보

| **필드명**              | **설명**                              |
| ----------------------- | ------------------------------------- |
| `user_id`               | 검증 미니게임에 참여한 유저 ID        |
| `picture_id`            | 검증 대상 사진 ID                     |
| `selected_candidate_id` | 유저가 정답으로 선택한 후보 종 ID     |
| `response_time`         | 응답 소요 시간 (매크로/어뷰징 방지용) |
| `created_at`            | 응답 등록 일시                        |

### 다이어그램

![](diagram.png)

### SQL

```sql
-- 1. Master Data 도메인
CREATE TABLE dictionary_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE dictionary (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_protected BOOLEAN DEFAULT FALSE,
    category_id INT REFERENCES dictionary_categories(id)
);

CREATE TABLE items_category (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category_id INT REFERENCES items_category(id)
);

CREATE TABLE terrarium_slot (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    category_id INT REFERENCES items_category(id)
);

-- 2. User & Inventory 도메인
CREATE TABLE users (
    id UUID PRIMARY KEY,
    xp INT DEFAULT 0,
    trust_score INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE user_inventory (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    item_id INT REFERENCES items(id),
    quantity INT DEFAULT 1,
    acquired_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (user_id, item_id)
);

CREATE TABLE user_terrarium (
    user_id UUID REFERENCES users(id),
    item_id INT REFERENCES items(id),
    slot_id INT REFERENCES terrarium_slot(id),
    PRIMARY KEY (user_id, slot_id),
    FOREIGN KEY (user_id, item_id) REFERENCES user_inventory(user_id, item_id)
);

-- 3. Quest 도메인 (다중 목표 추적 반영)
CREATE TABLE quest (
    id SERIAL PRIMARY KEY,
    description TEXT NOT NULL,
    reward_xp INT DEFAULT 0,
    expire_at TIMESTAMP WITH TIME ZONE DEFAULT date_trunc('day'::text, (now() + '2 days'::interval))
);

CREATE TABLE quest_reward (
    quest_id INT REFERENCES quest(id),
    item_id INT REFERENCES items(id),
    amount INT DEFAULT 0,
    PRIMARY KEY (quest_id, item_id)
);

CREATE TABLE target_dictionary (
    quest_id INT REFERENCES quest(id),
    dictionary_id INT REFERENCES dictionary(id),
    target_count INT DEFAULT 1,
    PRIMARY KEY (quest_id, dictionary_id)
);

CREATE TABLE target_dictionary_categories (
    quest_id INT REFERENCES quest(id),
    category_id INT REFERENCES dictionary_categories(id),
    target_count INT DEFAULT 1,
    PRIMARY KEY (quest_id, category_id)
);

CREATE TABLE user_quest (
    user_id UUID REFERENCES users(id),
    quest_id INT REFERENCES quest(id),
    status VARCHAR(20) DEFAULT 'in_progress',
    PRIMARY KEY (user_id, quest_id)
);

CREATE TABLE quest_progress_dictionary (
    user_id UUID,
    quest_id INT,
    dictionary_id INT REFERENCES dictionary(id),
    current_count INT DEFAULT 0,
    PRIMARY KEY (user_id, quest_id, dictionary_id),
    FOREIGN KEY (user_id, quest_id) REFERENCES user_quest(user_id, quest_id)
);

CREATE TABLE quest_progress_dictionary_categories (
    user_id UUID,
    quest_id INT,
    category_id INT REFERENCES dictionary_categories(id),
    current_count INT DEFAULT 0,
    PRIMARY KEY (user_id, quest_id, category_id),
    FOREIGN KEY (user_id, quest_id) REFERENCES user_quest(user_id, quest_id)
);

-- 4. Image & Trust 도메인
CREATE TABLE pictures (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    storage_url TEXT NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    candidate_dictionary_id INT REFERENCES dictionary(id),
    confirmed_dictionary_id INT REFERENCES dictionary(id)
);

CREATE TABLE picture_candidates (
    picture_id INT REFERENCES pictures(id) ON DELETE CASCADE,
    dictionary_id INT REFERENCES dictionary(id),
    confidence_score DOUBLE PRECISION,
    PRIMARY KEY (picture_id, dictionary_id)
);

CREATE TABLE picture_trust (
    user_id UUID REFERENCES users(id),
    picture_id INT REFERENCES pictures(id),
    selected_candidate_id INT REFERENCES dictionary(id),
    response_time INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, picture_id)
);
```

### Supabase 실행

![](supabase.png)

---

## 초기 데이터 구축 방안

- **생물종/분류 데이터**
  - 국가생물종목록 데이터 & 멸종위기종 목록 사용
    - 한반도 생물종 목록 데이터에서 생물 분류와 종의 국명을 분리해 에코퀘스트 생물 데이터로 사용한다.
    - 이때, 데이터 가공은 파이썬의 pandas 라이브러리를 사용하여 전처리를 진행한다.
    - 가공을 위해 작성한 `python` 코드는 다음과 같다. description 속성은 임시로 설명을 볼 수 있는 링크가 저장되도록 작업하였다.

      ```python
      import pandas as pd

      file = 'data.xlsx'

      spe = { '포유류': 1, '파충류': 2, '조류': 3, '양서류': 4, '어류': 5, '곤충류': 6 }

      res = []
      for sheet in spe:
          df = pd.read_excel(file, sheet_name=sheet, header=[0, 1])
          df = df[[('관리분류군', 'Unnamed: 2_level_1'), ('Species', '국명'), ('종 세부정보 URL', 'Unnamed: 30_level_1')]]
          df = df.dropna(subset=[('Species', '국명')])
          df = df[~df[('Species', '국명')].isin(['NaN', '[국명없음]'])]
          df.drop_duplicates(subset=[('Species', '국명')], inplace=True)

          df[('관리분류군', 'Unnamed: 2_level_1')] = df[('관리분류군', 'Unnamed: 2_level_1')].replace(spe)

          res.append(df)
      df = pd.concat(res, ignore_index=True)

      protected_df = pd.read_csv('protected_list.csv', encoding='cp949')[['국명', '등급']]
      protected_dict = protected_df.set_index('국명')['등급'].to_dict()

      df[('보호종_정보', '등급')] = df[('Species', '국명')].map(protected_dict)
      df[('보호종_정보', 'is_protected')] = df[('보호종_정보', '등급')].notna()

      df.drop(columns=[('보호종_정보', '등급')], inplace=True)

      # 헤더는 수동으로 수정하였음.
      df.to_csv('data.csv', index=False, encoding='utf-8-sig')
      ```

  - https://www.kbr.go.kr/content/view.do?menuKey=799&contentKey=174 (국가생물다양성센터)
  - https://www.data.go.kr/data/3071040/fileData.do (기후에너지환경부)
  - 다음은 Supabase에 가공한 데이터를 넣은 모습입니다.

  ![](init.png)

---

## 런타임 중 외부 데이터 사용 (추후 구현 예정)

- **날씨 데이터**
  - 기상청 단기예보 API 사용
    - 백엔드(서버리스 개발 시, 첫 접속이 일어난 프론트엔드)에서 날씨 데이터를 받아와 하드코딩된 퀘스트 풀에서 하나를 선택해 일일퀘스트를 생성한다.

  - https://www.data.go.kr/data/15084084/openapi.do

- **보호구역 여부**
  - V-World의 아생동식물보호 API 사용
    - 해당 좌표가 보호구역이라면 어떠한 보호구역인지 반환한다. 따라서 반환된 데이터가 없으면 정상 진행하고, 값이 반환되면 보호구역 예외 처리를 진행한다.

  - https://www.vworld.kr/dev/v4dv_2ddataguide2_s002.do?svcIde=um221

- **생물 사진**
  - **Gemini API**
    - 이미지를 AI에게 전달하고 결과를 JSON으로 받아오도록 프롬프팅을 작성한다. 이때, 이미지 용량이 비대하면 클라이언트에서 미리 압축 후 전달한다.

---

## Streamlit을 통한 DB 접근 테스트

![](streamlit.png)
