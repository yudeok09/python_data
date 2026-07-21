# 파이썬 데이터분석 종합실습 — 제출본

SKALA 광주 3반 유덕현 / 0720~0721 실습
교수님 요청에 따라 Day1·Day2 과제를 한 폴더로 합쳐 제출합니다.

## 폴더 구조

```
Python_data_0721_Day2/
├── practice1/실습1_로그_스트리밍집계.py        실습1. 20만 행 로그 스트리밍 집계 (제너레이터·fold)
├── practice2/실습2_스키마_검증.py              실습2. Pydantic v2 중첩 스키마 검증
├── practice3/실습3_비동기_수집기.py            실습3. asyncio 비동기 수집 (백프레셔·재시도)
├── practice4/                                  실습4. Pandas 정제
│   ├── 실습4_데이터_정제.py                    정제 5단계 + Copy-on-Write 동작 확인
│   └── test_실습4_데이터_정제.py               확장과제: 정제 규칙 테스트 (pytest 7개)
├── practice5/실습5_엔진_성능비교.py            실습5. Pandas·Polars·DuckDB + .explain() 실행계획
├── Total1/                                     종합실습1. 비동기 ETL 파이프라인
│   ├── 종합실습1_비동기ETL.py                  Extract·Transform·Load·run()
│   ├── 종합실습1_모델.py                       Pydantic 모델
│   └── test_종합실습1_비동기ETL.py             pytest 6개
├── Total2/종합실습2_EDA_통계_ML.py             종합실습2. EDA→시각화→통계검정→ML
├── Total3/                                     종합실습3. 분석 자동화 (관심사 분리)
│   ├── 종합실습3_설정.py                       불변 설정 (frozen dataclass)
│   ├── 종합실습3_리포트생성.py                 집계 + Jinja2 렌더링
│   ├── 종합실습3_실행_스케줄러.py              실행 방식 3가지 조율
│   ├── templates/report.html.j2                Jinja2 템플릿
│   └── test_종합실습3_리포트.py                pytest 4개
├── Advanced/                                   창의 과제 4종 (README.md 참고)
│   ├── 창의1_실시간_로그_이상탐지.py
│   ├── 창의2_매점_재고관리.py
│   ├── 창의3_이탈_조기경보.py
│   └── 창의4_SKALA_진도율_분석.py
├── data/                                       generate_data.py + 실습 데이터
└── screenshots/                                실행 캡처
```

## 실행 방법

```bash
# 프로젝트 루트(python_data)에서
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd Python_data_0721_Day2
python data/generate_data.py            # 데이터 생성 (seed=42 고정, 재현성)

python practice1/실습1_로그_스트리밍집계.py
python practice2/실습2_스키마_검증.py
python practice3/실습3_비동기_수집기.py
python practice3/실습3_비동기_수집기.py --real   # 실제 HTTP 수집
python practice4/실습4_데이터_정제.py
python practice5/실습5_엔진_성능비교.py
python Total1/종합실습1_비동기ETL.py
python Total2/종합실습2_EDA_통계_ML.py

# 종합3 — 같은 리포트를 3가지 방식으로 (결과는 동일)
python Total3/종합실습3_실행_스케줄러.py                            # 1회 생성
python Total3/종합실습3_실행_스케줄러.py --config region            # 설정만 바꿔 지역별
python Total3/종합실습3_실행_스케줄러.py --mode loop --interval 2 --count 3
python Total3/종합실습3_실행_스케줄러.py --mode schedule --interval 2 --count 2
python Total3/종합실습3_실행_스케줄러.py --mode cron                # crontab 등록용 출력

# 창의 과제
python Advanced/창의1_실시간_로그_이상탐지.py
python Advanced/창의2_매점_재고관리.py
python Advanced/창의3_이탈_조기경보.py
python Advanced/창의4_SKALA_진도율_분석.py

# 테스트 (총 21개)
cd Total1 && pytest -v && cd ..         # 6개
cd practice4 && pytest -v && cd ..      # 7개
cd Total3 && pytest -v && cd ..         # 4개
cd Advanced && pytest -v && cd ..       # 4개
ruff check .                            # 코드 검사
```

## 체크포인트 확인

| 과제 | 확인한 결과 |
| --- | --- |
| 실습1 | 총 200,000건 · 5xx 8.0% · reduce 재집계 일치 · 메모리 24.6MB → 0.17MB |
| 실습2 | 40건 → 유효 36 / 오염 4, 탈락 사유(필드+이유) 출력 |
| 실습3 | 60건 약 1.5초 (동기 환산 11초 대비 7배) · 재시도·dead-letter |
| 실습4 | 결측 516 → 0 · 수량 이상치 1995 → 16 · groupby/pivot/merge · 체인인덱싱 vs .loc 확인 |
| 실습5 | 3엔진 결과 완전 일치 · Polars 16ms < DuckDB 78ms < Pandas 284ms · pushdown 확인 |
| 종합1 | pytest 6개 PASSED · output에 CSV·Parquet 생성 |
| 종합2 | t-검정 p=1.23e-20 · 카이제곱 p=1.32e-70 · ROC-AUC 0.623 · Plotly 리포트 + joblib |
| 종합3 | 모듈 3분리 · KPI+매출표 HTML · 실행방식 3종 동일 결과 · pytest 4개 |
| 창의 | 4종 (로그 이상탐지 / 매점 관리 / 이탈 조기경보 / 우리 반 진도 코치) |

## 작업하면서 판단한 것들

**pandas 3.0 — copy_on_write 옵션**
가이드는 `pd.options.mode.copy_on_write = True`로 켜라고 하는데, 설치된 pandas 3.0에서는
이 옵션이 폐기되어(항상 켜짐) 그대로 쓰면 DeprecationWarning이 납니다. 그래서 옵션을 켜는
대신 체인 인덱싱과 `.loc`의 결과 차이를 직접 출력해 확인하는 쪽으로 바꿨습니다.

**가이드 예시 컬럼명과 실제 데이터**
가이드 예시는 고전 Telco 데이터셋 컬럼명(`Churn`, `MonthlyCharges`)을 쓰지만, 실제
`generate_data.py`가 만드는 데이터는 snake_case(`churn`(0/1), `monthly_charges`,
`tenure_months`)입니다. 실제 스키마에 맞춰 작성했습니다. 실습5의 `events_large.csv`에도
가이드 예시의 `status`/`value` 컬럼이 없어서 `amount > 0`인 거래를 `event_type`별로
집계하는 질의로 정의했습니다.

**표본이 작을 때의 검정 선택 (창의4)**
종합실습2에서는 카이제곱을 썼지만, 우리 반 10명 데이터에서는 기대빈도가 0.8까지 떨어져
카이제곱을 쓸 수 없었습니다. Fisher 정확검정과 Mann-Whitney U로 바꿔 계산했습니다.

## 가이드 폴더명 대응표

| 가이드 문서 | 제출 폴더 |
| --- | --- |
| ex01_streaming_agg | practice1 |
| ex02_pydantic_validation | practice2 |
| ex03_async_collector | practice3 |
| ex04_pandas_cleaning | practice4 |
| ex05_polars_duckdb | practice5 |
| capstone01_async_etl | Total1 |
| capstone02_eda_ml | Total2 |
| capstone03_automation | Total3 |
