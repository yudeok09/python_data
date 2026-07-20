# 실습2. Pydantic v2 중첩 스키마 검증
# api_response.json 40건 중에 일부러 망가뜨린 4건이 숨어있다
# → 규칙에 맞는 것만 통과시키고, 탈락한 건 "왜 탈락했는지"까지 남기기
# 실행: python practice2/validate_users.py

import json
from datetime import date
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, ValidationError, field_validator

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "api_response.json"


class Profile(BaseModel):
    # 중첩 구조의 안쪽 상자
    country: str
    tier: str
    score: float = Field(ge=0, le=100)  # 점수는 0~100. 150점은 없다


class User(BaseModel):
    id: int
    username: str
    email: str
    # Annotated 스타일: 타입힌트 자체에 검증 규칙을 붙인다 (아래 score의 = Field(...) 방식과 같은 효과)
    age: Annotated[int, Field(ge=0, le=120)]  # 음수 나이 차단
    is_active: bool
    signup_date: date  # 문자열 "2024-07-02"를 알아서 date로 바꿔줌
    profile: Profile  # 모델 안에 모델
    tags: list[str] = Field(default_factory=list)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        # email-validator 패키지까지 쓰긴 과해서 골뱅이만 확인
        v = v.strip()
        if "@" not in v:
            raise ValueError("이메일에 @가 없음")
        return v

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        return v.strip()  # 검증 겸 정규화. 반드시 return 할 것


def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    users = data["results"]  # 실제 레코드는 results 안에 있음
    print(f"응답 status={data['status']}, 전체 {len(users)}건 검사 시작\n")

    valid, invalid = [], []
    for i, row in enumerate(users):
        try:
            valid.append(User(**row))
        except ValidationError as e:
            # 한 건 터졌다고 멈추면 안 됨. 기록하고 다음 건으로
            invalid.append({"index": i, "id": row.get("id", "?"), "errors": e.errors()})

    print(f"결과: 유효 {len(valid)}건 / 오염 {len(invalid)}건")

    print("\n[탈락 사유]")
    print(f"{'id':<5}{'필드':<16}{'사유'}")
    print("-" * 50)
    for item in invalid:
        for err in item["errors"]:
            loc = ".".join(str(x) for x in err["loc"])  # 중첩이면 profile.score 식으로
            print(f"{item['id']:<5}{loc:<16}{err['msg']}")

    # 통과한 데이터로 간단 요약도 하나 (검증 후 데이터는 믿고 쓸 수 있다는 것)
    actives = [u for u in valid if u.is_active]
    avg_score = sum(u.profile.score for u in valid) / len(valid)
    print(
        f"\n[검증 통과분 요약] 활성 사용자 {len(actives)}명, 평균 score {avg_score:.1f}"
    )

    by_tier = {}
    for u in valid:
        by_tier[u.profile.tier] = by_tier.get(u.profile.tier, 0) + 1
    print(f"tier 분포: {by_tier}")


if __name__ == "__main__":
    main()
