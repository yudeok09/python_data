# Python_data_0721_Day2

SKALA 광주 3반 유덕현 / 0720~0721 데이터분석 실습 — Day2 제출

## 폴더 구조

```
Python_data_0721_Day2/
├── practice4/clean_sales.py       실습4. Pandas 정제 (결측·이상치·타입) + groupby/pivot/merge
├── practice5/engine_benchmark.py  실습5. Pandas·Polars·DuckDB 성능비교 + 결과일치 검증
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
python practice5/engine_benchmark.py
python Total2/analysis.py
python Total3/run_scheduler.py          # 리포트 1회 생성
python Total3/run_scheduler.py --config region       # 지역별 설정으로
python Total3/run_scheduler.py --interval 2 --count 3 # 주기 반복(Ctrl+C 중지)
cd Total3 && pytest -v                  # 테스트 4개
python Advanced/churn_early_warning.py
```

## 체크포인트 확인

- 실습4: 결측 516건 → 0건, quantity 이상치 1995 → 16 (IQR 윈저라이징), groupby/pivot/merge 출력
- 실습5: 3엔진 결과 완전 일치(assert_frame_equal 통과), Polars < DuckDB < Pandas
- 종합2: t-검정 p=1.23e-20, 카이제곱 p=1.32e-70 (둘 다 유의), ROC-AUC=0.623
- 종합2 산출물: Plotly HTML 리포트 + joblib 모델(전처리 포함, compress)
- 종합3: config/report/scheduler 모듈 분리, Jinja2 렌더링, pytest 4개 PASSED
- Advanced: 모델 로드 → 200명 점수화 → 기대손실 기준 리텐션 우선순위 CSV

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
