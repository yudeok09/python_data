# python_data — 파이썬 데이터분석 종합실습

SKALA 광주 3반 유덕현 / 0720~0721 데이터분석 실습 제출용

## 폴더 구조

```
Python_data_0720_Day1/
├── practice1/log_report.py       실습1. 로그 20만행 스트리밍 집계 (제너레이터, one-pass)
├── practice2/validate_users.py   실습2. Pydantic v2 검증 — 오염 4건 분리
├── practice3/async_collector.py  실습3. asyncio 수집기 (세마포어/재시도/백오프)
├── Total1/                       종합실습1. 비동기 ETL 파이프라인 + pytest 6개
│   ├── models.py  pipeline.py  test_pipeline.py
├── Advanced/log_watchdog.py      [창의] 슬라이딩 윈도우 5xx 이상 탐지
├── data/                         실습용 데이터
└── screenshots/                  실행 결과 캡처 6장

Python_data_0721_Day2/            (Day2 — 실습4·5, 종합실습2·3 예정)
```

## 실행 방법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd Python_data_0720_Day1
python practice1/log_report.py
python practice2/validate_users.py
python practice3/async_collector.py
python Total1/pipeline.py
cd Total1 && pytest -v        # 테스트 6개
python Advanced/log_watchdog.py
```

## 체크포인트 확인

- 실습1: 총 200,000건 / 5xx 8.0%
- 실습2: 40건 → 유효 36 / 오염 4
- 실습3: 60건 약 1.5초 (동기 환산 11초 대비 7배↑)
- 종합1: pytest 6개 PASSED, output/에 CSV·Parquet 생성
- 코드 검사: `ruff check Python_data_0720_Day1` 통과
