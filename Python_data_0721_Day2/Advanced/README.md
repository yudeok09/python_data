# [창의 과제] churn_early_warning.py — 이탈 조기경보 · 리텐션 우선순위

종합2에서 저장한 모델(`churn_model.joblib`)을 실제로 불러와 "배포"해보는 과제입니다.
모델을 만드는 것과 쓰는 것은 다르다는 걸 보여주려고 만들었습니다.

핵심 아이디어 — **단순 이탈확률 순이 아니라 기대손실(이탈확률 × 월요금) 순으로 우선순위**를 매깁니다.
확률 0.9인 저가 고객보다 확률 0.5인 고가 고객을 먼저 잡는 게 회사엔 이득이니까요.
한정된 상담원을 어디에 투입할지 정하는 실전 관점입니다.

- `joblib.load`로 전처리 포함 Pipeline 통째로 로드 → 새 고객 바로 점수화
- 위험도 3단계(🔴🟡🟢) 분류 + 오늘 전화할 TOP 10 우선순위
- 상담팀 배포용 `output/retention_priority.csv` 생성 (엑셀 한글 안 깨지게 utf-8-sig)

실행: `python Advanced/churn_early_warning.py`
(먼저 `python Total2/analysis.py`로 모델을 생성해야 합니다)
