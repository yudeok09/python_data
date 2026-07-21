# 실습3. asyncio 기반 비동기 수집기
# 기본값은 인터넷 없이 실행되는 모의 수집이다.
# USE_REAL_HTTP=True 또는 --real 옵션을 사용하면 실제 공개 API를 호출한다.
#
# 모의 실행: python practice3/실습3_비동기_수집기.py
# 실제 실행: python practice3/실습3_비동기_수집기.py --real

import argparse
import asyncio
import json
import random
import time
from pathlib import Path

import httpx

USE_REAL_HTTP = False
TOTAL = 60
MAX_CONCURRENT = 10
FAIL_RATE = 0.08
REAL_API_URL = "https://jsonplaceholder.typicode.com/posts/{item_id}"


async def fetch_mock(item_id: int) -> dict:
    """응답 지연과 일시 오류가 있는 가짜 API 호출"""
    await asyncio.sleep(random.uniform(0.1, 0.25))
    if random.random() < FAIL_RATE:
        raise ConnectionError(f"item {item_id}: 일시적인 모의 서버 오류")
    return {
        "id": item_id,
        "value": round(random.uniform(1, 100), 2),
        "source": "mock",
        "ok": True,
    }


async def fetch_real(client: httpx.AsyncClient, item_id: int) -> dict:
    """JSONPlaceholder 공개 API에서 실제 HTTP 응답을 수집"""
    api_id = item_id + 1
    response = await client.get(REAL_API_URL.format(item_id=api_id))
    response.raise_for_status()
    data = response.json()
    return {
        "id": item_id,
        "api_id": data["id"],
        "title": data["title"],
        "source": "jsonplaceholder",
        "ok": True,
    }


def fetch_sync(item_id: int) -> dict:
    time.sleep(0.18)
    return {"id": item_id, "ok": True}


def run_sync_sample(total: int, sample_size: int = 12) -> tuple[float, float]:
    sample_size = min(sample_size, total)
    start = time.perf_counter()
    for i in range(sample_size):
        fetch_sync(i)
    elapsed = time.perf_counter() - start
    return elapsed, elapsed * (total / sample_size)


async def collect_one(
    item_id: int,
    sem: asyncio.Semaphore,
    retry_log: list[tuple[int, int, float]],
    client: httpx.AsyncClient | None = None,
    max_retries: int = 3,
) -> dict:
    for attempt in range(max_retries):
        try:
            async with sem:
                async with asyncio.timeout(5.0):
                    if client is None:
                        return await fetch_mock(item_id)
                    return await fetch_real(client, item_id)
        except (ConnectionError, TimeoutError, httpx.HTTPError) as error:
            if attempt == max_retries - 1:
                return {"id": item_id, "ok": False, "error": str(error)}

            wait = 0.3 * (2**attempt)
            retry_log.append((item_id, attempt + 1, round(wait, 1)))
            await asyncio.sleep(wait)


async def collect(
    total: int = TOTAL,
    max_concurrent: int = MAX_CONCURRENT,
    use_real_http: bool = USE_REAL_HTTP,
) -> tuple[list[dict], list[dict], list[tuple[int, int, float]]]:
    sem = asyncio.Semaphore(max_concurrent)
    retry_log: list[tuple[int, int, float]] = []

    if use_real_http:
        timeout = httpx.Timeout(5.0)
        headers = {"User-Agent": "SKALA-async-practice/1.0"}
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            tasks = [collect_one(i, sem, retry_log, client) for i in range(total)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
    else:
        tasks = [collect_one(i, sem, retry_log) for i in range(total)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    ok = [r for r in results if isinstance(r, dict) and r.get("ok")]
    fail = [r for r in results if not (isinstance(r, dict) and r.get("ok"))]
    return ok, fail, retry_log


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="asyncio 비동기 수집기")
    parser.add_argument(
        "--real",
        action="store_true",
        help="모의 데이터 대신 JSONPlaceholder 공개 API를 호출합니다.",
    )
    parser.add_argument("--total", type=int, default=TOTAL, help="수집할 데이터 개수")
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=MAX_CONCURRENT,
        help="동시 요청 제한",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    use_real_http = USE_REAL_HTTP or args.real

    if args.total < 1:
        raise ValueError("수집 개수는 1 이상이어야 합니다.")
    if use_real_http and args.total > 100:
        raise ValueError("JSONPlaceholder posts는 최대 100건까지 제공합니다.")
    if args.max_concurrent < 1:
        raise ValueError("동시 요청 제한은 1 이상이어야 합니다.")

    mode = "실제 HTTP" if use_real_http else "모의"
    print(f"수집 대상 {args.total}건 / 동시 제한 {args.max_concurrent} / {mode} 모드")
    print("-" * 58)

    estimated_sync = None
    if not use_real_http:
        sample_time, estimated_sync = run_sync_sample(args.total)
        print(
            f"[동기]   {min(12, args.total)}건 실측 {sample_time:.2f}초 "
            f"→ {args.total}건 환산 약 {estimated_sync:.1f}초"
        )

    random.seed(42)
    start = time.perf_counter()
    ok, fail, retry_log = asyncio.run(
        collect(args.total, args.max_concurrent, use_real_http)
    )
    elapsed = time.perf_counter() - start

    if estimated_sync is None:
        print(f"[실제 HTTP 비동기] {args.total}건 {elapsed:.2f}초")
    else:
        print(
            f"[비동기] {args.total}건 실제 {elapsed:.2f}초 "
            f"(약 {estimated_sync / elapsed:.1f}배 빠름)"
        )
    print(f"\n성공 {len(ok)}건 / 최종 실패 {len(fail)}건")

    if retry_log:
        print(f"재시도 발생 {len(retry_log)}회 (지수 백오프로 복구):")
        for item_id, nth, wait in retry_log:
            print(f"  - item {item_id}: {nth}차 실패 → {wait}초 쉬고 다시 시도")

    if fail:
        dead_path = Path(__file__).resolve().parent / "dead_letter.json"
        dead_path.write_text(
            json.dumps(fail, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"실패 건은 {dead_path.name}에 기록했습니다.")

    sample = sorted(ok, key=lambda row: row["id"])[:3]
    print(f"\n수집 결과 샘플: {sample}")


if __name__ == "__main__":
    main()
