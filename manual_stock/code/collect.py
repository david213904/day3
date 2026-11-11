"""
collect.py — ① 시세 받기  ② 가공(정리 + 지표 계산)

yfinance로 종목별 '1시간 봉'(시가·고가·저가·종가·거래량)을 받아서
pandas로 정리하고 등락률 · 이동평균 · 신호를 계산해 DB에 넣을 행으로 만든다.
※ 교육용 예제입니다. yfinance 시세는 15~20분 늦을 수 있고, 투자 판단용이 아닙니다.
"""
import random
from datetime import datetime, timedelta, timezone

import pandas as pd

KST = timezone(timedelta(hours=9))

NAMES = {"005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "035420.KS": "NAVER",
         "035720.KS": "카카오", "005380.KS": "현대차"}


# ─────────────────────────────────────────────
# ① 받기 — yfinance (키 필요 없음)
# ─────────────────────────────────────────────
def fetch_yf(ticker: str) -> pd.DataFrame:
    """최근 한 달치 1시간 봉. 매번 한 달치를 받아 덮어쓰면 이동평균이 항상 정확하다."""
    import yfinance as yf
    df = yf.Ticker(ticker).history(period="1mo", interval="1h")
    if df.empty:
        raise RuntimeError(f"{ticker}: 시세가 비어 있습니다 (종목코드·장 휴일 확인)")
    return df


# ─────────────────────────────────────────────
# ①' 연습용 가짜 시세 — yfinance가 막혀도 실습할 수 있게
# ─────────────────────────────────────────────
def fetch_demo(ticker: str) -> pd.DataFrame:
    rnd = random.Random(ticker)                      # 종목마다 늘 같은 흐름
    price = {"005930.KS": 70000, "000660.KS": 180000}.get(ticker, 50000) * 1.0
    now = datetime.now(KST)
    day = (now - timedelta(days=31)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = []
    while day <= now:
        if day.weekday() < 5:                        # 평일만 장이 열림
            for h in range(9, 16):                   # 09시 ~ 15시 봉
                ts = day.replace(hour=h)
                if ts > now:
                    break
                o = price
                c = o * (1 + rnd.gauss(0.0003, 0.008))
                hi = max(o, c) * (1 + abs(rnd.gauss(0, 0.003)))
                lo = min(o, c) * (1 - abs(rnd.gauss(0, 0.003)))
                vol = int(abs(rnd.gauss(1, 0.4)) * 500000)
                rows.append({"Datetime": ts, "Open": o, "High": hi, "Low": lo, "Close": c, "Volume": vol})
                price = c
        day += timedelta(days=1)
    df = pd.DataFrame(rows).set_index("Datetime")
    # 진짜 데이터처럼 '덜 끝난 봉(거래량 0)'과 빈칸을 일부러 섞는다
    if len(df) > 10:
        df.iloc[-1, df.columns.get_loc("Volume")] = 0
        df.iloc[len(df) // 2, df.columns.get_loc("Close")] = float("nan")
    return df


# ─────────────────────────────────────────────
# ② 가공 — 정리 + 지표
# ─────────────────────────────────────────────
def clean(df: pd.DataFrame, ticker: str, source: str, spike_pct: float = 1.5):
    stats = {"fetched": len(df), "dropped": 0, "cleaned": 0}
    df = df.copy()

    # 1) 필요한 칸만, 이름은 소문자로
    df = df[["Open", "High", "Low", "Close", "Volume"]].rename(columns=str.lower)

    # 2) 종가가 비었거나 0 이하인 봉은 버린다
    before = len(df)
    df = df[df["close"].notna() & (df["close"] > 0)]
    stats["dropped"] = before - len(df)

    # 3) 원화는 소수점이 없다 → 정수로
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].round().astype("int64")
    df["volume"] = df["volume"].fillna(0).astype("int64")

    # 4) 시각을 한국 시간으로 통일하고 순서대로
    idx = pd.to_datetime(df.index)
    idx = idx.tz_localize(KST) if idx.tz is None else idx.tz_convert(KST)
    df.index = idx
    df = df.sort_index()

    # 5) 지표: 직전 봉 대비 등락률, 5시간·20시간 이동평균
    df["change_pct"] = (df["close"].pct_change() * 100).round(2)
    df["ma5"] = df["close"].rolling(5).mean().round(0)
    df["ma20"] = df["close"].rolling(20).mean().round(0)

    # 6) 신호: 이동평균이 엇갈린 순간 + 한 시간에 크게 움직인 순간
    above = df["ma5"] > df["ma20"]
    crossed = above.ne(above.shift()) & df["ma20"].notna() & df["ma20"].shift().notna()
    df["signal"] = None
    df.loc[crossed & above, "signal"] = "골든크로스"
    df.loc[crossed & ~above, "signal"] = "데드크로스"
    df.loc[df["signal"].isna() & (df["change_pct"].abs() >= spike_pct), "signal"] = "급변동"

    # 7) DB 행으로. 아직 진행 중인 마지막 봉도 넣지만, 다음 수집 때 같은 시각으로 덮어써진다
    rows = []
    for ts, r in df.iterrows():
        rows.append({
            "source": source, "ticker": ticker, "name": NAMES.get(ticker, ticker),
            "ts": ts.isoformat(),
            "open": int(r.open), "high": int(r.high), "low": int(r.low), "close": int(r.close),
            "volume": int(r.volume),
            "change_pct": None if pd.isna(r.change_pct) else float(r.change_pct),
            "ma5": None if pd.isna(r.ma5) else float(r.ma5),
            "ma20": None if pd.isna(r.ma20) else float(r.ma20),
            "signal": r.signal if isinstance(r.signal, str) else None,
        })
    stats["cleaned"] = len(rows)
    return rows, stats
