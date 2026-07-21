# 종합실습3 - 스케줄러 (관심사 분리: '언제 부를지'만 결정)
# 자기가 직접 집계하지 않는다. report.generate_report를 언제 부를지만 정한다.
# 이렇게 나눠두면 실행 주기를 바꿔도 집계 로직(report.py)은 안 건드린다.
#
# 한 번 실행(채점용): python Total3/run_scheduler.py
# 지역별 리포트    : python Total3/run_scheduler.py --config region
# 주기 반복(3회)   : python Total3/run_scheduler.py --interval 2 --count 3   (Ctrl+C로 중지)

import argparse
import time
from datetime import datetime

from config import BY_REGION, DEFAULT
from report import generate_report

CONFIGS = {"default": DEFAULT, "region": BY_REGION}


def run_once(config) -> None:
    path = generate_report(config)
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] '{config.title}' 생성 → {path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="리포트 자동 생성 스케줄러")
    parser.add_argument(
        "--config", choices=CONFIGS, default="default", help="사용할 설정"
    )
    parser.add_argument("--interval", type=int, help="반복 주기(초). 주면 반복 모드")
    parser.add_argument(
        "--count", type=int, default=1, help="반복 횟수 (interval과 함께)"
    )
    args = parser.parse_args()

    config = CONFIGS[args.config]

    if args.interval is None:
        # 기본: 한 번만 생성하고 끝 (채점 시 멈추지 않게)
        run_once(config)
        return

    # 반복 모드: interval초 간격으로 count번 생성
    print(f"스케줄 시작: {args.interval}초 간격 · {args.count}회 (Ctrl+C로 중지)")
    try:
        for i in range(args.count):
            run_once(config)
            if i < args.count - 1:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n사용자 중지(Ctrl+C). 스케줄러 종료.")


if __name__ == "__main__":
    main()
