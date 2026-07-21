# 종합실습3 - 스케줄러 (관심사 분리: '언제 부를지'만 결정)
# 자기가 직접 집계하지 않는다. report.generate_report를 언제 부를지만 정한다.
# 이렇게 나눠두면 실행 주기를 바꿔도 집계 로직(report.py)은 안 건드린다.
#
# 실행 방식 3가지 — 어디서 돌리든 결과 리포트는 똑같이 나온다:
#   loop     : 의존성 없이 sleep으로 도는 경량 루프 (개발중 확인용)
#   schedule : schedule 라이브러리로 주기를 선언적으로 지정
#   cron     : OS crontab에 등록할 한 줄을 뽑아준다 (서버 무인 실행용)
#
# 한 번만 실행(채점용): python Total3/run_scheduler.py
# 지역별 리포트       : python Total3/run_scheduler.py --config region
# 경량 루프           : python Total3/run_scheduler.py --mode loop --interval 2 --count 3
# schedule 라이브러리 : python Total3/run_scheduler.py --mode schedule --interval 2 --count 2
# cron 등록용 한 줄   : python Total3/run_scheduler.py --mode cron

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from config import BY_REGION, DEFAULT
from report import generate_report

CONFIGS = {"default": DEFAULT, "region": BY_REGION}


def run_once(config, retries: int = 2) -> None:
    # 확장과제(실패 재시도): 무인 실행이라 아무도 안 보고 있다.
    # 디스크가 잠깐 바쁘거나 파일이 잠겨서 실패할 수 있으니 몇 번 다시 해본다.
    for attempt in range(retries + 1):
        try:
            path = generate_report(config)
            stamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{stamp}] '{config.title}' 생성 → {path.name}")
            return
        except Exception as e:
            if attempt == retries:
                print(
                    f"[실패] {retries + 1}번 시도했지만 안 됨: {type(e).__name__}: {e}"
                )
                raise
            wait = 2**attempt
            print(
                f"[재시도] {type(e).__name__} 발생 → {wait}초 후 다시 ({attempt + 1}/{retries})"
            )
            time.sleep(wait)


def run_loop(config, interval: int, count: int) -> None:
    # 방식1. 경량 루프. 라이브러리 없이 sleep으로만 돈다.
    print(f"[loop] {interval}초 간격 · {count}회 (Ctrl+C로 중지)")
    try:
        for i in range(count):
            run_once(config)
            if i < count - 1:
                time.sleep(interval)
    except KeyboardInterrupt:
        print("\n사용자 중지(Ctrl+C).")


def run_schedule(config, interval: int, count: int) -> None:
    # 방식2. schedule 라이브러리. "몇 초마다 이걸 해라"를 선언만 해두고
    # run_pending()이 때가 됐는지 봐준다. 매일 09:00 같은 표현도 한 줄로 된다.
    try:
        import schedule
    except ImportError:
        print(
            "schedule 라이브러리가 없습니다. pip install schedule 후 다시 실행하세요."
        )
        return

    done = {"n": 0}

    def job():
        run_once(config)
        done["n"] += 1

    schedule.every(interval).seconds.do(job)
    # 실무에선 이렇게 쓴다 → schedule.every().day.at("09:00").do(job)

    print(f"[schedule] every({interval}).seconds 등록 · {count}회까지 (Ctrl+C로 중지)")
    try:
        while done["n"] < count:
            schedule.run_pending()
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n사용자 중지(Ctrl+C).")
    finally:
        schedule.clear()


def print_cron(config) -> None:
    # 방식3. OS cron. 파이썬이 계속 떠 있을 필요 없이 OS가 시간 맞춰 깨워준다.
    # crontab을 코드가 멋대로 건드리면 위험하니 등록할 한 줄만 뽑아준다.
    here = Path(__file__).resolve()
    python = Path(sys.executable)
    log = here.parent / "output" / "cron.log"
    line = f'0 9 * * * cd "{here.parent}" && "{python}" {here.name} --config default >> "{log}" 2>&1'

    print("[cron] 매일 오전 9시 실행하려면 아래 한 줄을 crontab에 넣으면 된다.")
    print("\n  등록:  crontab -e   (편집기에서 붙여넣기)")
    print("  확인:  crontab -l")
    print(f"\n{line}\n")
    print("  분 시 일 월 요일  →  '0 9 * * *' = 매일 09시 00분")
    print("  루프/스케줄러와 달리 프로세스를 계속 띄워둘 필요가 없다.")

    # 현재 등록된 crontab이 있는지만 확인 (수정은 하지 않는다)
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        has = (
            "등록된 항목 있음"
            if r.returncode == 0 and r.stdout.strip()
            else "등록된 항목 없음"
        )
        print(f"  현재 사용자 crontab: {has}")
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="리포트 자동 생성 스케줄러")
    parser.add_argument(
        "--config", choices=CONFIGS, default="default", help="사용할 설정"
    )
    parser.add_argument(
        "--mode",
        choices=["once", "loop", "schedule", "cron"],
        default="once",
        help="실행 방식 (기본 once = 한 번 생성하고 종료)",
    )
    parser.add_argument("--interval", type=int, help="반복 주기(초)")
    parser.add_argument("--count", type=int, default=1, help="반복 횟수")
    args = parser.parse_args()

    config = CONFIGS[args.config]

    # --interval만 주면 알아서 루프 모드로 (예전 사용법 그대로 동작하게)
    mode = args.mode
    if mode == "once" and args.interval is not None:
        mode = "loop"

    if mode == "cron":
        print_cron(config)
    elif mode == "once":
        run_once(config)  # 채점 시 멈추지 않게 기본은 1회
    else:
        interval = args.interval or config.interval_seconds
        count = max(args.count, 1)
        (run_loop if mode == "loop" else run_schedule)(config, interval, count)


if __name__ == "__main__":
    main()
