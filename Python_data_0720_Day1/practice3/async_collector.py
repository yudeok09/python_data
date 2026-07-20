# 실습3. asyncio 기반 비동기 수집기
# 60건을 하나씩 기다리면 한참 걸리는데, 동시에 던지면 1~2초면 끝난다.
# 대신 무작정 다 던지면 서버가 죽으니까 Semaphore로 동시 10개 제한 + 실패시 재시도.
# USE_REAL_HTTP=False 라서 인터넷 없이 모의(mock)로 돈다.
# 실행: python practice3/async_collector.py

import asyncio
import json
import random
import time
from pathlib import Path

USE_REAL_HTTP = False  # 진짜 API 없으니 False 고정. httpx 쓸 일 있으면 여기만 바꾸면 됨
TOTAL = 60
MAX_CONCURRENT = 10
FAIL_RATE = 0.08  # 8% 확률로 일부러 실패시켜서 재시도 로직 테스트

random.seed(42)  # 결과 재현되게


async def fetch_mock(item_id: int) -> dict:
    """가짜 API 호출. 0.1~0.25초 걸리고 가끔 터진다 (현실 반영)"""
    await asyncio.sleep(random.uniform(0.1, 0.25))
    if random.random() < FAIL_RATE:
        raise ConnectionError(f"item {item_id}: 서버가 잠깐 삐끗함")
    return {"id": item_id, "value": round(random.uniform(1, 100), 2), "ok": True}


# ---------- 동기 버전 (비교용) ----------
def fetch_sync(item_id: int) -> dict:
    time.sleep(0.18)  # 평균 대기시간이랑 비슷하게
    return {"id": item_id, "ok": True}


def run_sync_sample(n=12):
    # 60개 다 돌리면 10초 넘게 걸려서 12개만 재고 5배로 환산했다
    start = time.perf_counter()
    for i in range(n):
        fetch_sync(i)
    elapsed = time.perf_counter() - start
    return elapsed, elapsed * (TOTAL / n)


# ---------- 비동기 수집기 본체 ----------
sem = asyncio.Semaphore(MAX_CONCURRENT)  # 입장권 10장
retry_log = []  # 어떤 애가 몇 번 삐끗했는지 기록


async def collect_one(item_id: int, max_retries=3) -> dict:
    for attempt in range(max_retries):
        try:
            async with sem:  # 입장권 없으면 여기서 줄 서서 대기
                async with asyncio.timeout(2.0):  # 2초 넘게 안 오면 포기
                    return await fetch_mock(item_id)
        except (ConnectionError, TimeoutError) as e:
            if attempt == max_retries - 1:
                # 3번 다 실패 → 포기하고 실패 기록으로 반환
                return {"id": item_id, "ok": False, "error": str(e)}
            wait = 0.3 * (2**attempt)  # 0.3 → 0.6 → 1.2초 (지수 백오프)
            retry_log.append((item_id, attempt + 1, round(wait, 1)))
            await asyncio.sleep(wait)


async def main():
    tasks = [collect_one(i) for i in range(TOTAL)]  # 아직 실행 전, 예약만
    results = await asyncio.gather(
        *tasks, return_exceptions=True
    )  # 하나 터져도 전체는 산다

    ok = [r for r in results if isinstance(r, dict) and r.get("ok")]
    fail = [r for r in results if not (isinstance(r, dict) and r.get("ok"))]
    return ok, fail


if __name__ == "__main__":
    print(
        f"수집 대상 {TOTAL}건 / 동시 제한 {MAX_CONCURRENT} / 실패율 {FAIL_RATE:.0%} (모의)"
    )
    print("-" * 50)

    # 1. 동기 방식이 얼마나 느린지부터
    sample_t, est = run_sync_sample()
    print(f"[동기]   12건 실측 {sample_t:.2f}초 → 60건 환산 약 {est:.1f}초")

    # 2. 비동기 수집
    start = time.perf_counter()
    ok, fail = asyncio.run(main())
    elapsed = time.perf_counter() - start

    print(f"[비동기] 60건 실제 {elapsed:.2f}초  (약 {est / elapsed:.1f}배 빠름)")
    print(f"\n성공 {len(ok)}건 / 최종 실패 {len(fail)}건")

    if retry_log:
        print(f"재시도 발생 {len(retry_log)}회 (지수 백오프로 복구):")
        for item_id, nth, wait in retry_log:
            print(f"  - item {item_id}: {nth}차 실패 → {wait}초 쉬고 다시 시도")

    # 3. 확장과제: 재시도까지 다 해도 안 된 건 dead_letter로 격리
    #    실패를 조용히 버리면 나중에 원인 추적이 안 되니까 파일로 남긴다
    if fail:
        dead_path = Path(__file__).resolve().parent / "dead_letter.json"
        dead_path.write_text(
            json.dumps(fail, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"실패 건은 {dead_path.name} 에 기록해둠 (나중에 재처리용)")

    sample = sorted(ok, key=lambda r: r["id"])[:3]
    print(f"\n수집 결과 샘플: {sample}")
