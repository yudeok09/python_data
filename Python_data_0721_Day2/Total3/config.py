# 종합실습3 - 설정 (관심사 분리: '값'만 담당)
# frozen=True → 만든 뒤엔 아무도 못 바꾼다. 설정이 프로그램 중간에 몰래 바뀌면
# "분명 A로 설정했는데 왜 B로 돌지?"라는 최악의 버그가 생기는데, 그걸 원천 차단.

from dataclasses import dataclass
from pathlib import Path

BASE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ReportConfig:
    data_path: Path
    output_dir: Path
    title: str = "일일 매출 요약 리포트"
    group_by: str = "category"  # 이 컬럼만 바꾸면 지역별/카테고리별로 리포트가 바뀐다
    top_n: int = 5
    interval_seconds: int = 3600  # 스케줄 주기 (기본 1시간)


# 기본 설정. 다른 리포트가 필요하면 이 값만 바꾸거나 새 ReportConfig를 만들면 된다.
DEFAULT = ReportConfig(
    data_path=BASE.parent / "data" / "sales_raw.csv",
    output_dir=BASE / "output",
)

# 예시: 지역별 리포트가 필요하면 이렇게 (report.py는 한 줄도 안 고쳐도 됨)
BY_REGION = ReportConfig(
    data_path=BASE.parent / "data" / "sales_raw.csv",
    output_dir=BASE / "output",
    title="지역별 매출 요약 리포트",
    group_by="region",
)
