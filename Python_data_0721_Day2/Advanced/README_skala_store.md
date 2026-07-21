# [창의 과제] SKALA 매점 상품관리 대시보드

SKALA 매점 사장이 커피, 얼음컵, 과자, 음료, 간편식의 재고를 쉽게 관리할 수 있도록 만든 프로젝트입니다.

## 수업 내용과 연결한 부분

- 실습2 Pydantic: 음수 재고, 0원 가격, 누락 상품명을 자동 검증
- 실습3 asyncio: 매대·창고·공급업체 데이터를 동시에 수집
- 종합실습1 ETL: Extract → Transform → Load 구조로 분리
- 창의 기능: Plotly 그래프, 관리자 경고, 상품별 해결 방향, 처리 완료 체크

## 실행 방법

프로젝트 최상위 폴더에서 실행합니다.

```bash
python Python_data_0720_Day1/Advanced/창의2_매점_재고관리.py
```

실행 후 `Advanced/output/store_dashboard.html`을 브라우저에서 열면 됩니다.

테스트는 다음 명령으로 실행합니다.

```bash
cd Python_data_0720_Day1/Advanced
pytest -v test_skala_store_manager.py
```

## 생성되는 결과

- `store_dashboard.html`: 재고 그래프와 관리자 경고 대시보드
- `admin_alerts.csv`: 발견된 문제와 해결 방향
- `cleaned_products.csv`: 검증을 통과한 상품
- `invalid_products.csv`: 수정이 필요한 원본 데이터

## 판단 규칙

- 재고가 0개이면 즉시 발주
- 재고가 발주 기준 이하이거나 2일분 미만이면 7일 판매분을 계산해 발주량 추천
- 유통기한이 임박했는데 재고가 많으면 할인·1+1 행사 추천
- 이전 가격보다 20% 이상 변하면 가격표와 입고가 확인
- 판매가 없거나 30일분 이상 재고가 있으면 추가 발주 보류와 행사 추천
- 데이터 자체가 잘못되면 상품을 분석에서 제외하고 수정 방법 안내

모든 상품과 수치는 수업용으로 만든 가상 데이터입니다.
