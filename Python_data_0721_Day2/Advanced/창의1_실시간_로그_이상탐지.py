# [창의 과제] 실시간 로그 이상 탐지 워치독
# ----------------------------------------------
# 실습1에서 로그를 "다 읽고 나서" 집계했는데, 실무 모니터링은 반대로
# "흘러가는 중에" 이상을 잡아야 한다. 그래서 web_logs.csv 20만 행을
# 실시간 스트림처럼 재생하면서,
#   - 최근 300건 슬라이딩 윈도우로 5xx 비율을 계속 감시
#   - 평소(8%)보다 확 튀는 순간(12% 이상)에 ALERT 발생
#   - 알람 순간에 어떤 경로에서 5xx가 몰렸는지 스냅샷
# 을 찍는다. 실무였으면 print 대신 슬랙 웹훅을 쏘면 되는 구조.
# 마지막엔 시간대별 트래픽을 ASCII 차트로 그려준다 (터미널 낭만)
#
# 실행: python Advanced/창의1_실시간_로그_이상탐지.py

import csv
from collections import Counter, deque
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "web_logs.csv"

WINDOW = 300  # 최근 300건만 본다
THRESHOLD = 0.12  # 5xx가 12% 넘으면 이상 상황으로 판단 (평소 8%)
CHECK_EVERY = 100  # 매 행마다 검사하면 낭비라 100행마다
COOLDOWN = 3000  # 알람 한 번 울리면 3000행 지날 때까지 재알람 금지 (알람 폭탄 방지)


def stream_logs(path):
    with open(path, newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def watch():
    window = deque()  # (is_5xx, path) 튜플로 최근 300건 유지
    err_in_window = 0
    last_alert_at = -COOLDOWN
    alerts = []

    total = 0
    by_hour = Counter()
    by_status = Counter()

    print(
        f"감시 시작: 윈도우 {WINDOW}건 / 임계치 {THRESHOLD:.0%} / 쿨다운 {COOLDOWN}행"
    )
    print("=" * 56)

    for row in stream_logs(LOG_PATH):
        total += 1
        by_hour[row["timestamp"][11:13]] += 1
        by_status[row["status"]] += 1

        is_err = row["status"].startswith("5")
        window.append((is_err, row["path"]))
        err_in_window += is_err
        if len(window) > WINDOW:
            old_err, _ = window.popleft()
            err_in_window -= old_err

        # 윈도우가 다 찼을 때만, 100행마다 검사
        if len(window) == WINDOW and total % CHECK_EVERY == 0:
            ratio = err_in_window / WINDOW
            if ratio >= THRESHOLD and total - last_alert_at >= COOLDOWN:
                last_alert_at = total
                # 이 순간 윈도우 안에서 5xx가 몰린 경로 스냅샷
                hot = Counter(p for e, p in window if e).most_common(3)
                alerts.append((row["timestamp"], ratio))
                print(
                    f"🚨 ALERT #{len(alerts)}  {row['timestamp']}  "
                    f"최근 {WINDOW}건 중 5xx {ratio:.1%} (평소 8%)"
                )
                for path, cnt in hot:
                    print(f"     └ {path:<20} 5xx {cnt}건")

    return total, by_hour, by_status, alerts


def draw_hourly_chart(by_hour, total):
    # matplotlib 없이 터미널에서 바로 보는 시간대별 트래픽
    print("\n[시간대별 트래픽]")
    peak = max(by_hour.values())
    for h in sorted(by_hour):
        cnt = by_hour[h]
        bar = "█" * round(cnt / peak * 40)
        print(f"  {h}시 {bar} {cnt:,}")


if __name__ == "__main__":
    total, by_hour, by_status, alerts = watch()

    if not alerts:
        print("(감시 구간 내 임계치 초과 없음 — 오늘은 평화로운 날)")

    print("=" * 56)
    err = sum(c for s, c in by_status.items() if s.startswith("5"))
    print(
        f"감시 종료. 총 {total:,}건 처리 / 전체 5xx {err / total:.1%} / 알람 {len(alerts)}회"
    )
    if alerts:
        worst_ts, worst = max(alerts, key=lambda a: a[1])
        print(
            f"최악 구간: {worst_ts} ({worst:.1%}) ← 실무면 이 시각 배포내역부터 뒤진다"
        )

    draw_hourly_chart(by_hour, total)
