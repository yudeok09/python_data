# Python_data_0721_Day2

SKALA 광주 3반 유덕현 / 0720~0721 데이터분석 실습 — Day2 제출

## 폴더 구조

```
Python_data_0721_Day2/
├── practice4/                     실습4. Pandas 정제 (결측·이상치·타입) + groupby/pivot/merge
│   ├── clean_sales.py             정제 5단계 + Copy-on-Write 동작 확인
│   └── test_clean_sales.py        확장과제: 정제 규칙 함수화·테스트 (pytest 7개)
├── practice5/engine_benchmark.py  실습5. 3엔진 성능비교 + 결과일치 + .explain() 실행계획
├── Total2/                        종합실습2. EDA→시각화→통계검정→ML
│   ├── analysis.py                (Polars EDA, Plotly 리포트, t검정·카이제곱, RandomForest)
│   └── output/                    eda_report.html, churn_model.joblib
├── Total3/                        종합실습3. 분석 자동화 (관심사 분리)
│   ├── config.py                  불변 설정 (frozen dataclass)
│   ├── report.py                  집계 + Jinja2 렌더링
│   ├── run_scheduler.py           주기 실행 조율
│   ├── templates/report.html.j2   Jinja2 템플릿
│   └── test_report.py             pytest 4개
├── Advanced/                      창의 과제
│   └── churn_early_warning.py     joblib 모델 배포 → 리텐션 우선순위 시뮬레이터
├── data/                          generate_data.py + 실습 데이터
└── screenshots/                   실행 캡처
```

## 실행 방법

```bash
# 프로젝트 루트(python_data)에서 가상환경 활성화 후
cd Python_data_0721_Day2
python data/generate_data.py            # 데이터 생성 (seed=42, 재현성)

python practice4/clean_sales.py
cd practice4 && pytest -v && cd ..      # 정제 규칙 테스트 7개 (확장과제)
python practice5/engine_benchmark.py
python Total2/analysis.py

# 종합3 — 같은 리포트를 3가지 방식으로 실행 (결과는 동일)
python Total3/run_scheduler.py                             # 1회 생성 (채점용)
python Total3/run_scheduler.py --config region             # 설정만 바꿔 지역별로
python Total3/run_scheduler.py --mode loop --interval 2 --count 3      # 경량 루프
python Total3/run_scheduler.py --mode schedule --interval 2 --count 2  # schedule 라이브러리
python Total3/run_scheduler.py --mode cron                 # crontab 등록용 한 줄 출력
cd Total3 && pytest -v && cd ..         # 테스트 4개

python Advanced/churn_early_warning.py
```

## 체크포인트 확인

- 실습4: 결측 516건 → 0건, quantity 이상치 1995 → 16 (IQR 윈저라이징), groupby/pivot/merge 출력
- 실습4: Copy-on-Write — 체인 인덱싱은 원본이 안 바뀌고 `.loc`은 바뀌는 것을 실행으로 확인
- 실습4 확장: 정제 규칙 함수화 + pytest 7개 PASSED
- 실습5: 3엔진 결과 완전 일치(assert_frame_equal 통과), Polars < DuckDB < Pandas
- 실습5: `.explain()` 실행계획에 `PROJECT 2/5 COLUMNS`, `SELECTION` 이 스캔 단계에 찍힘(pushdown 확인)
- 종합2: t-검정 p=1.23e-20, 카이제곱 p=1.32e-70 (둘 다 유의), ROC-AUC=0.623
- 종합2 산출물: Plotly HTML 리포트 + joblib 모델(전처리 포함, compress)
- 종합3: config/report/scheduler 모듈 분리, Jinja2 렌더링, pytest 4개 PASSED
- 종합3: 타임스탬프 HTML에 KPI 4종 + 그룹별 매출표(비중 막대) 렌더링
- 종합3: 실행 방식 3가지(경량 루프 · schedule · OS cron) 모두 동일 리포트 생성, 실패 재시도 포함
- Advanced: 모델 로드 → 200명 점수화 → 기대손실 기준 리텐션 우선순위 CSV

### pandas 3.0 관련 메모

가이드는 `pd.options.mode.copy_on_write = True` 로 CoW를 켜라고 하는데, 지금 설치된
pandas 3.0에서는 이 옵션이 폐기(항상 켜짐)되어 그대로 쓰면 DeprecationWarning이 납니다.
그래서 옵션을 켜는 대신 체인 인덱싱과 `.loc` 의 동작 차이를 직접 출력해 확인하도록 했습니다.

## 참고 — 가이드 예시 컬럼명과 실제 데이터

가이드 예시 코드는 고전 Telco 데이터셋 컬럼명(`Churn`, `MonthlyCharges` 등)을 쓰지만,
실제 `generate_data.py`가 만드는 데이터는 snake_case(`churn`(0/1), `monthly_charges`,
`tenure_months` 등)입니다. 실제 데이터 스키마에 맞춰 작성했습니다.

| 가이드 폴더            | 제출 폴더 |
| ---------------------- | --------- |
| ex04_pandas_cleaning   | practice4 |
| ex05_polars_duckdb     | practice5 |
| capstone02_eda_ml      | Total2    |
| capstone03_automation  | Total3    |
