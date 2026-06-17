# 연구용 생물 위치 정보 데이터 추출 도구 (export.py) 가이드

본 문서는 서비스로 누적된 생물 관찰 데이터를 공간 분석(GIS), 생태 연구, 생물다양성 통계 모델링 등에 바로 활용할 수 있도록 가공하여 CSV 형식으로 내보내는 독립 도구인 `export.py`에 대한 상세한 매뉴얼 및 통계적 산출 공식 설명서입니다.

---

## 1. 개요

`export.py`는 에코퀘스트(EcoQuest) 웹 서비스 외부에서 독자적인 Python CLI 명령으로 데이터베이스 서버와 직접 트랜잭션하여 위치 정보 및 검증 상태가 포함된 생태 관찰 레코드를 CSV로 가공 추출하는 도구입니다.

기존 데이터베이스의 날것(Raw) 상태 데이터에 사진 검증 통계 알고리즘을 실시간 연산 적용하여, 연구원들이 신뢰 등급과 통계적 유의성 수치가 포함된 지리 공간 분석 데이터셋을 획득할 수 있도록 돕습니다.

---

## 2. 사용 방법 (CLI Usage)

본 도구는 Python 가상환경 내에서 명령어 라인 인자(CLI arguments)를 지정하여 실행합니다.

```bash
# 기본 실행 (전체 위치 관찰 데이터 추출)
./bin/python3 export.py -o ./exported_data.csv

# 특정 필터 조건 조합 실행 예시
# 예: 검증 완료된 '조류' 카테고리의 법정 보호종만 지정 경로로 추출
./bin/python3 export.py --confirmed-only --category "조류" --protected-only -o ./birds_protected_export.csv

# 특정 기간 동안 수집된 데이터 필터링
./bin/python3 export.py --start-date "2026-06-01" --end-date "2026-06-30" -o ./june_biodiversity.csv
```

### 옵션 파라미터 상세 설명

| **명령어 인자**    | **축약형** | **타입** | **기본값**                         | **설명**                                                |
| :----------------- | :--------- | :------- | :--------------------------------- | :------------------------------------------------------ |
| `--output`         | `-o`       | String   | `./exported_biodiversity_data.csv` | 생성 및 저장될 CSV 파일 경로                            |
| `--confirmed-only` |            | Flag     | `False` (인자 사용 시 `True`)      | 다수결 합의에 의해 검증 확정된 사진만 내보냄            |
| `--category`       | `-c`       | String   | `None` (전체)                      | 특정 분류군 필터링 (예: 조류, 곤충류, 어류 등)          |
| `--protected-only` |            | Flag     | `False` (인자 사용 시 `True`)      | 법정 보호종(`is_protected=True`) 데이터만 내보냄        |
| `--start-date`     |            | String   | `None` (전체)                      | YYYY-MM-DD 형식의 관찰 조회 시작일                      |
| `--end-date`       |            | String   | `None` (전체)                      | YYYY-MM-DD 형식의 관찰 조회 종료일 (당일 23:59:59 포함) |

---

## 3. 출력 CSV 데이터 명세 (Output Schema)

추출되는 CSV 파일은 엑셀, R, pandas, GIS 툴(QGIS, ArcGIS 등)에서 한글 깨짐 없이 로드될 수 있도록 **UTF-8-SIG** 인코딩 포맷을 채택하고 있으며, 컬럼 구성은 다음과 같습니다.

| **컬럼명**       | **타입**  | **설명**                                                                   |
| :--------------- | :-------- | :------------------------------------------------------------------------- |
| `observation_id` | Integer   | 관찰 사진 고유 번호 (`pictures.id`)                                        |
| `species_name`   | String    | 최종 매칭된 생물종 명칭 (예: '까치')                                       |
| `category_name`  | String    | 생물 분류군 카테고리 (예: '조류', '곤충류')                                |
| `is_protected`   | Boolean   | 법정 보호종 여부 (`True` / `False`)                                        |
| `latitude`       | Float     | 촬영 위도 (WGS84 GPS 좌표)                                                 |
| `longitude`      | Float     | 촬영 경도 (WGS84 GPS 좌표)                                                 |
| `is_confirmed`   | Boolean   | 다수결 모델에 의해 최종 확정(`confirmed_dictionary_id` 존재) 여부          |
| `confidence`     | Float     | 해당 생물종의 **수학적 베이지안 사후 확률** (투표가 없으면 AI 점수로 대체) |
| `p_value`        | Float     | 이항 검정에 의한 유의확률 ($p$-value, 투표가 없으면 `1.0` 적용)            |
| `vote_count`     | Integer   | 해당 사진에 누적된 총 유효 투표수 ($N$, 비정상 응답시간 필터링 반영)       |
| `observed_at`    | Timestamp | 사진 업로드 일시 (`YYYY-MM-DD HH:MM:SS` 로컬 문자열 형식)                  |

---

## 4. 통계적 신뢰도 산출 알고리즘 및 수식

연구 데이터의 질적 관리를 위해, `export.py`는 데이터베이스 상의 단순 합의 수치 대신 아래의 통계 모델을 실시간 연산 적용합니다.

### 1) 베이지안 사후 확률 (Bayesian Posterior)

미니게임 투표 이력(`picture_trust`) 및 각 유저의 평판 점수(`users.trust_score`)를 연계하여 실시간으로 계산합니다.

- **Prior (사전 확률)**: AI의 각 후보종 예측 신뢰도 점수 $C_k$를 정규화하여 사용합니다.
  $$P(s_k) = \frac{C_k}{\sum_{j=1}^{M} C_j}$$
- **Likelihood (우도)**: 유저 $i$의 신뢰도 상관계수 $\rho_i$가 있을 때, 해당 유저가 올바른 답을 선택할 확률 $p_i$는 다음과 같습니다.
  $$p_i = \max\left(0.0, \frac{1}{M} + \left(1.0 - \frac{1}{M}\right)\rho_i\right)$$
  - 만약 유저가 정답 $s_k$를 지지하면 $P(v_i | s_k) = p_i$, 오답을 선택하면 $P(v_i | s_k) = \frac{1 - p_i}{M - 1}$ 로 우도를 누적 곱 연산합니다.
- **Posterior (사후 확률, confidence)**:
  $$P(s_k | \mathbf{v}) = \frac{P(s_k) \prod_{i=1}^{N} P(v_i | s_k)}{\sum_{j=1}^{M} P(s_j) \prod_{i=1}^{N} P(v_i | s_j)}$$
- **예외(Fallback)**: 해당 사진에 아직 투표한 인원이 없을 경우($N=0$), AI가 매칭한 해당 종의 확신 점수(Confidence Score)를 그대로 `confidence` 값으로 대체합니다.

### 2) 이항 검정 유의확률 (Binomial p-value)

다수결의 통계적 우연성을 검정합니다.

- 귀무가설 $H_0$: "사용자들이 무작위(확률 $p_0 = \frac{1}{M}$)로 선택지를 찍었다."
- 총 투표수 $N$ 및 해당 생물종 득표수 $K$ 하에서, 우연히 $K$번 이상 동일한 선택지를 고를 확률($p$-value)을 계산합니다.
  $$p\text{-value} = \sum_{x=K}^{N} \binom{N}{x} (p_0)^x (1 - p_0)^{N - x}$$
- $p$-value가 임계치(예: 0.05)보다 낮을수록 해당 관찰의 검증 합의 결과가 과학적으로 유의미함을 뜻합니다. 투표가 없는 데이터는 `1.0`을 부여합니다.

---

## 5. 데이터 무결성 및 전처리

- **GPS 누락 배제**: 위치 기반 분석(GIS)에 즉시 임포트할 수 있도록, 위도(`latitude`) 혹은 경도(`longitude`) 좌표값 중 하나라도 `NULL`인 데이터는 데이터 조회 단계(`SQL WHERE`)에서 원천 배제됩니다.
- **비정상 투표 필터링**: 응답 속도가 500ms 미만인 매크로성 반응이나 300,000ms(5분)를 초과한 이탈 반응은 `picture_trust` 연산 대상에서 사전에 배제하여 통계적 신뢰성을 강화합니다.
- **트레일링 데이터 보호**: 회원 탈퇴 등으로 유저 계정이 지워지더라도 관찰 사진 데이터와 투표 기록은 남겨지도록 하는 스키마 정책(`ON DELETE SET NULL`)에 부합하여, 업로더 정보가 `NULL`로 변경된 관찰 내역 또한 소실 없이 연구용 데이터로 내보낼 수 있도록 설계되었습니다.

---

## 6. 연구 분석 사용례 (Use Cases & Analysis Examples)

내보낸 CSV 데이터를 생태 분석에 활용하는 Python pandas 및 QGIS 활용법 예제입니다.

### 1) Python Pandas: 데이터 전처리 및 통계적 필터링

특정 신뢰성(사후 확률 95% 이상 및 유의 수준 $p < 0.05$)을 충족하는 데이터만 걸러내어 요약 통계를 산출하는 예제입니다.

```python
import pandas as pd

# CSV 데이터 로드 (UTF-8-SIG 고려)
df = pd.read_csv("./exported_biodiversity_data.csv", encoding="utf-8-sig")

# 통계적 신뢰 기준 필터링 (신뢰도 95% 이상 및 유의확률 5% 미만)
valid_research_data = df[(df["confidence"] >= 0.95) & (df["p_value"] < 0.05)]

print(f"전체 관찰 수: {len(df)} | 신뢰 연구 데이터 수: {len(valid_research_data)}")

# 분류 카테고리별 보호종 수 집계
summary = valid_research_data.groupby("category_name")["is_protected"].sum()
print("\n[카테고리별 수집된 보호종 개체 수]")
print(summary)
```

### 2) Python Matplotlib & Seaborn: 공간 분포 시각화

위도와 경도 좌표를 사용하여 생물종 분포 지도를 2D 산점도(Scatter Plot)로 빠르게 렌더링하는 방법입니다.

```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

df = pd.read_csv("./exported_biodiversity_data.csv", encoding="utf-8-sig")
research_df = df[df["confidence"] >= 0.90] # 90% 이상 신뢰도

plt.figure(figsize=(10, 8))
sns.scatterplot(
    data=research_df,
    x="longitude",
    y="latitude",
    hue="category_name",
    size="confidence",
    sizes=(20, 200),
    alpha=0.7
)
plt.title("Spatial Distribution of Observed Species (EcoQuest)")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.grid(True)
plt.show()
```

### 3) GIS 소프트웨어 (QGIS) 연동 안내

1. QGIS를 실행하고 **[레이어] ➡️ [레이어 추가] ➡️ [구분자로 분리된 텍스트 레이어 추가...]** 메뉴를 클릭합니다.
2. 파일 이름에 내보낸 `exported_biodiversity_data.csv` 경로를 지정합니다.
3. 인코딩 형식을 **System** 또는 **UTF-8**로 선택합니다.
4. 도형 정의에서 **포인트 좌표**를 선택하고, **X 필드**에 `longitude`, **Y 필드**에 `latitude`를 지정합니다.
5. 좌표계(CRS)를 **EPSG:4326 - WGS 84**로 지정한 후 [추가]를 누르면, 생물의 발견 위치가 공간 레이어로 투영되어 배경 지도(V-World, OpenStreetMap 등) 위에 정확하게 시각화됩니다.
