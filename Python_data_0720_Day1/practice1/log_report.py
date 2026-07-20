# 실습1. 대용량 로그 스트리밍 집계
# web_logs.csv 20만행을 통째로 안 올리고 한 번만 훑어서 리포트 뽑기
# 실행: python practice1/log_report.py

import csv
import time
import tracemalloc
from collections import Counter
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "web_logs.csv"


def read_logs(path):
    """한 줄씩 dict로 흘려보내는 제너레이터. return 말고 yield!"""
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            yield row


def aggregate(path):
    # 루프는 딱 한 번. 지나가면서 카운터 4개를 같이 채운다
    total = 0
    by_status = Counter()
    by_path = Counter()
    by_hour = Counter()
    by_ip = Counter()

    for row in read_logs(path):
        total += 1
        by_status[row["status"]] += 1
        by_path[row["path"]] += 1
        by_ip[row["ip"]] += 1
        # timestamp가 2025-03-01T00:00:05 형태라서 11:13이 시(HH)
        by_hour[row["timestamp"][11:13]] += 1

    return total, by_status, by_path, by_hour, by_ip


def print_report(total, by_status, by_path, by_hour, by_ip):
    err_5xx = sum(c for s, c in by_status.items() if s.startswith("5"))
    ratio = err_5xx / total * 100

    print("=" * 46)
    print("  web_logs.csv 접속 로그 리포트")
    print("=" * 46)
    print(f"총 요청 수  : {total:,}")
    print(f"5xx 오류    : {err_5xx:,}건 ({ratio:.1f}%)")

    print("\n[상태코드별]")
    for s, c in sorted(by_status.items()):
        print(f"  {s}  {c:>7,}  ({c / total * 100:4.1f}%)")

    print("\n[인기 경로 TOP 5]")
    for p, c in by_path.most_common(5):
        print(f"  {p:<20} {c:>7,}")

    print("\n[시간대별 요청수 (많은 순 TOP 5)]")
    for h, c in by_hour.most_common(5):
        print(f"  {h}시  {c:>7,}")

    print("\n[접속 상위 IP TOP 5]")
    for ip, c in by_ip.most_common(5):
        print(f"  {ip:<16} {c:>5,}")


def memory_compare(path):
    # 확장과제: readlines() vs 제너레이터 메모리 실측
    # 말로만 "메모리 적게 씀" 하면 안 와닿아서 직접 재봤다
    tracemalloc.start()
    lines = open(path, encoding="utf-8").readlines()
    _ = len(lines)
    _, peak_list = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del lines

    tracemalloc.start()
    cnt = 0
    for _row in read_logs(path):
        cnt += 1
    _, peak_gen = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print("\n[확장] 메모리 비교 (tracemalloc peak)")
    print(f"  readlines() 방식 : {peak_list / 1024 / 1024:8.2f} MB")
    print(f"  제너레이터 방식  : {peak_gen / 1024 / 1024:8.2f} MB")
    print(
        f"  → 약 {peak_list / peak_gen:,.0f}배 차이. 행이 2억개면 위 방식은 그냥 죽는다"
    )


if __name__ == "__main__":
    start = time.perf_counter()
    total, *counters = aggregate(LOG_PATH)
    elapsed = time.perf_counter() - start

    print_report(total, *counters)
    print(f"\n집계 시간: {elapsed:.2f}초 (one-pass)")

    memory_compare(LOG_PATH)
