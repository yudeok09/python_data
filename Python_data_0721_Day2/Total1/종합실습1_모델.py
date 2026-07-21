# 종합실습1 - Pydantic 모델 (실습2에서 배운 거 재사용)
# 검증 규칙을 여기 한 곳에 모아두면 pipeline 쪽은 규칙을 몰라도 된다

from pydantic import BaseModel, Field, field_validator


class Seller(BaseModel):
    seller_id: int
    region: str

    @field_validator("region")
    @classmethod
    def region_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("판매자 지역이 비어있음")
        return v


class Product(BaseModel):
    id: int
    name: str
    category: str
    price: float = Field(gt=0)  # 음수/0원 상품 거부
    quantity: int = Field(ge=0, le=10_000)  # 재고는 0~1만 사이만 정상으로 본다
    seller: Seller  # 중첩 모델
    tags: list[str] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        # " Food " 처럼 지저분하게 들어와도 뒷단에선 항상 "food"만 보게
        v = v.strip().lower()
        if not v:
            raise ValueError("category 비어있음")
        return v
