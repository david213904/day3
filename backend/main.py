import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# 로컬에선 .env를 읽고, Railway에선 Variables가 이미 들어 있음
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]
FRONT_ORIGINS = [
    o.strip() for o in os.getenv("FRONT_ORIGINS", "").split(",") if o.strip()
]

sb = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

app = FastAPI(title="my-api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONT_ORIGINS,
    # 내 컴퓨터의 아무 포트 + 내 Vercel 팀(jeju-ax)의 jeju-market 배포 주소(미리보기 포함)
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+|https://jeju-market(-[a-z0-9-]+)?-jeju-ax\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


class ItemIn(BaseModel):
    name: str

@app.get("/v")
def health():
    return {"status": "uuuuuuuu"}


class ItemIn(BaseModel):
    name: str


@app.get("/items")
def list_items():
    try:
        res = sb.table("items").select("*").order("id", desc=True).limit(50).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase 오류: {e}")
    return res.data


@app.post("/items")
def create_item(item: ItemIn):
    try:
        res = sb.table("items").insert({"name": item.name}).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase 오류: {e}")
    return res.data[0]


# ───────────────────────── 장바구니 (제주 마켓) ─────────────────────────
# 상품 목록은 서버가 가진다. 가격을 화면에서 받으면 조작될 수 있기 때문.
PRODUCTS = [
    {"id": "hallabong", "name": "한라봉 3kg", "price": 24000, "emoji": "🍊", "desc": "향긋하고 달콤한 제주 대표 감귤", "tag": "과일"},
    {"id": "gamgyul-choco", "name": "감귤 초콜릿", "price": 9800, "emoji": "🍫", "desc": "귤 향이 가득한 선물용 초콜릿", "tag": "간식"},
    {"id": "omegi", "name": "오메기떡 10입", "price": 15000, "emoji": "🍡", "desc": "쫄깃한 제주 전통 떡", "tag": "간식"},
    {"id": "heukdwaeji", "name": "흑돼지 오겹살 600g", "price": 32000, "emoji": "🥓", "desc": "육즙 가득 제주 흑돼지", "tag": "정육"},
    {"id": "galchi", "name": "제주 은갈치 2미", "price": 38000, "emoji": "🐟", "desc": "은빛 싱싱한 갈치 세트", "tag": "수산"},
    {"id": "green-tea", "name": "한라산 녹차 티백", "price": 12000, "emoji": "🍵", "desc": "깊고 부드러운 녹차 30입", "tag": "차"},
    {"id": "tangerine-juice", "name": "감귤 착즙주스 10병", "price": 19000, "emoji": "🧃", "desc": "100% 감귤 원액 착즙", "tag": "음료"},
    {"id": "dolhareubang", "name": "돌하르방 미니 피규어", "price": 7500, "emoji": "🗿", "desc": "제주 여행 기념 소품", "tag": "기념품"},
    {"id": "jeju-honey", "name": "제주 꿀 500g", "price": 18000, "emoji": "🍯", "desc": "제주 자연에서 채취한 순수 꿀", "tag": "식품"},
]
PRODUCT_MAP = {p["id"]: p for p in PRODUCTS}
MAX_QTY = 99


class CartAdd(BaseModel):
    product_id: str
    qty: int = Field(default=1, ge=1, le=MAX_QTY)


class CartQty(BaseModel):
    qty: int = Field(ge=1, le=MAX_QTY)


def _check_cart_id(cart_id: str):
    # 브라우저가 만든 랜덤 문자열(UUID 등)만 허용
    if not (8 <= len(cart_id) <= 64) or not all(c.isalnum() or c in "-_" for c in cart_id):
        raise HTTPException(status_code=400, detail="cart_id 형식이 올바르지 않습니다.")


def _cart_view(cart_id: str):
    try:
        rows = sb.table("cart_items").select("product_id, qty").eq("cart_id", cart_id).order("created_at").execute().data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase 오류: {e}")
    items, total, count = [], 0, 0
    for r in rows:
        p = PRODUCT_MAP.get(r["product_id"])
        if not p:  # 판매 종료된 상품은 건너뜀
            continue
        line = p["price"] * r["qty"]
        items.append({**p, "qty": r["qty"], "line_total": line})
        total += line
        count += r["qty"]
    return {"cart_id": cart_id, "items": items, "total": total, "count": count}


@app.get("/products")
def list_products():
    return PRODUCTS


@app.get("/cart/{cart_id}")
def get_cart(cart_id: str):
    _check_cart_id(cart_id)
    return _cart_view(cart_id)


@app.post("/cart/{cart_id}/items")
def add_to_cart(cart_id: str, body: CartAdd):
    _check_cart_id(cart_id)
    if body.product_id not in PRODUCT_MAP:
        raise HTTPException(status_code=404, detail="없는 상품입니다.")
    try:
        cur = sb.table("cart_items").select("qty").eq("cart_id", cart_id).eq("product_id", body.product_id).execute().data
        qty = min(MAX_QTY, (cur[0]["qty"] if cur else 0) + body.qty)
        sb.table("cart_items").upsert(
            {"cart_id": cart_id, "product_id": body.product_id, "qty": qty},
            on_conflict="cart_id,product_id",
        ).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase 오류: {e}")
    return _cart_view(cart_id)


@app.patch("/cart/{cart_id}/items/{product_id}")
def set_qty(cart_id: str, product_id: str, body: CartQty):
    _check_cart_id(cart_id)
    try:
        sb.table("cart_items").update({"qty": body.qty}).eq("cart_id", cart_id).eq("product_id", product_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase 오류: {e}")
    return _cart_view(cart_id)


@app.delete("/cart/{cart_id}/items/{product_id}")
def remove_from_cart(cart_id: str, product_id: str):
    _check_cart_id(cart_id)
    try:
        sb.table("cart_items").delete().eq("cart_id", cart_id).eq("product_id", product_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase 오류: {e}")
    return _cart_view(cart_id)


@app.delete("/cart/{cart_id}")
def clear_cart(cart_id: str):
    _check_cart_id(cart_id)
    try:
        sb.table("cart_items").delete().eq("cart_id", cart_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase 오류: {e}")
    return _cart_view(cart_id)
