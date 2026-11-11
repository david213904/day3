"""
main.py — 주식 1시간 봉 백엔드 (FastAPI)  ※ 교육용 예제, 투자 판단용 아님

   yfinance ──① 받기──▶ FastAPI ──② 정리·지표 계산──▶ ④ Supabase 저장
                           ▲
   Vercel(React) ── 그래프용 데이터만 요청 ──┘

Railway Variables
  SUPABASE_URL, SUPABASE_SECRET_KEY   Supabase 연결 (없으면 메모리 임시 저장)
  ADMIN_TOKEN                         /collect 를 아무나 못 누르게 하는 암호
  FRONT_ORIGINS                       Vercel 주소 (쉼표로 여러 개)
  TICKERS=005930.KS,000660.KS,035420.KS   종목 (야후 코드: 코스피 .KS · 코스닥 .KQ)
  DEMO_MODE=0     1 이면 가짜 시세 (yfinance가 막혔을 때)
  COLLECT_MINUTES=60  SPIKE_PCT=1.5  AUTO_COLLECT=1
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import collect
import db

log = logging.getLogger("uvicorn.error")

TICKERS = [t.strip().upper() for t in os.getenv("TICKERS", "005930.KS,000660.KS,035420.KS").split(",") if t.strip()]
DEMO = os.getenv("DEMO_MODE", "0") == "1"
SOURCE = "demo" if DEMO else "yfinance"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()
AUTO = os.getenv("AUTO_COLLECT", "1") == "1"
MINUTES = int(os.getenv("COLLECT_MINUTES", "60"))
SPIKE = float(os.getenv("SPIKE_PCT", "1.5"))
FRONT_ORIGINS = [o.strip().rstrip("/") for o in os.getenv("FRONT_ORIGINS", "").split(",") if o.strip()]

store = db.get_store()


# ─────────── 수집 한 번 = 종목마다 받기 → 정리·지표 → 저장, 그리고 기록 ───────────
def run_collect() -> dict:
    total = {"fetched": 0, "dropped": 0, "cleaned": 0, "saved": 0}
    errors = []
    for t in TICKERS:
        try:
            raw = collect.fetch_demo(t) if DEMO else collect.fetch_yf(t)
            rows, st = collect.clean(raw, t, SOURCE, SPIKE)
            saved = store.save_candles(rows)
            for k in ["fetched", "dropped", "cleaned"]:
                total[k] += st[k]
            total["saved"] += saved
        except Exception as e:                      # 한 종목이 실패해도 나머지는 계속
            errors.append(f"{t}: {e}"[:200])
    entry = {"ran_at": datetime.now(timezone.utc).isoformat(), "source": SOURCE,
             "tickers": len(TICKERS), **total, "error": "; ".join(errors) or None}
    store.save_log(entry)
    log.info("collect %s", entry)
    return entry


async def auto_loop():
    """서버가 켜져 있는 동안 COLLECT_MINUTES 마다 자동 수집 (브라우저가 꺼져 있어도)"""
    while True:
        try:
            await asyncio.to_thread(run_collect)
        except Exception:
            log.exception("자동 수집 실패")
        await asyncio.sleep(MINUTES * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(auto_loop()) if AUTO else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="주식 1시간 봉 백엔드 (교육용)", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=FRONT_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])


def _view(r):
    return {"time": db.kst(r["ts"]), "open": r["open"], "high": r["high"], "low": r["low"],
            "close": r["close"], "volume": r["volume"], "change_pct": r["change_pct"],
            "ma5": r["ma5"], "ma20": r["ma20"], "signal": r["signal"]}


@app.get("/")
def home():
    return {"service": "주식 1시간 봉 백엔드 (교육용)", "mode": SOURCE, "docs": "/docs"}


@app.get("/health")
def health():
    missing = [k for k in ["SUPABASE_URL", "SUPABASE_SECRET_KEY", "ADMIN_TOKEN", "FRONT_ORIGINS"]
               if not os.getenv(k, "").strip()]
    return {"ok": True, "mode": SOURCE, "store": store.kind, "tickers": TICKERS,
            "auto_collect_minutes": MINUTES if AUTO else None, "missing": missing}


@app.post("/collect")
def collect_now(x_admin_token: str = Header(default="")):
    """지금 바로 한 번 수집 (Swagger /docs 에서 Try it out)"""
    if not ADMIN_TOKEN:
        raise HTTPException(503, "Railway Variables에 ADMIN_TOKEN을 먼저 넣으세요")
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401, "x-admin-token이 틀렸습니다")
    return run_collect()


@app.get("/stocks")
def stocks():
    """종목별 마지막 봉 요약 (목록 화면용)"""
    out = []
    for t in TICKERS:
        rs = store.candles(SOURCE, t, 2)
        if not rs:
            out.append({"ticker": t, "name": collect.NAMES.get(t, t), "ready": False})
            continue
        last = rs[-1]
        out.append({"ticker": t, "name": last["name"], "ready": True, **_view(last)})
    return out


@app.get("/stocks/{ticker}/candles")
def candles(ticker: str, limit: int = 120):
    """그래프용 1시간 봉 (오래된 것 → 최신 순)"""
    rs = store.candles(SOURCE, ticker.upper(), min(max(limit, 1), 500))
    if not rs:
        raise HTTPException(404, f"{ticker} 데이터가 없습니다 (TICKERS 확인 · /collect 실행)")
    return {"ticker": ticker.upper(), "name": rs[-1]["name"], "mode": SOURCE,
            "candles": [_view(r) for r in rs]}


@app.get("/stocks/{ticker}/signals")
def signals(ticker: str):
    """골든크로스 · 데드크로스 · 급변동이 있었던 시각만"""
    rs = store.candles(SOURCE, ticker.upper(), 500)
    return [_view(r) for r in rs if r["signal"]][-30:]


@app.get("/logs")
def logs():
    return store.logs()
