"""
db.py — ④ 저장: Supabase (변수가 없으면 서버 메모리에 임시 저장)
"""
import os
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def kst(ts: str) -> str:
    return datetime.fromisoformat(ts).astimezone(KST).strftime("%Y-%m-%d %H:%M")


class SupabaseStore:
    kind = "supabase"

    def __init__(self, url, key):
        from supabase import create_client
        self.sb = create_client(url, key)

    def save_candles(self, rows):
        if not rows:
            return 0
        saved = 0
        for i in range(0, len(rows), 500):           # 한 번에 너무 많이 보내지 않게 나눠서
            res = (self.sb.table("candles")
                   .upsert(rows[i:i + 500], on_conflict="source,ticker,ts").execute())
            saved += len(res.data or [])
        return saved

    def save_log(self, log):
        self.sb.table("stock_logs").insert(log).execute()

    def candles(self, source, ticker, limit=150):
        res = (self.sb.table("candles").select("*").eq("source", source).eq("ticker", ticker)
               .order("ts", desc=True).limit(limit).execute())
        return list(reversed(res.data))

    def logs(self, limit=20):
        res = (self.sb.table("stock_logs").select("*")
               .order("ran_at", desc=True).limit(limit).execute())
        return res.data


class MemoryStore:
    kind = "memory(임시)"

    def __init__(self):
        self.rows, self._logs = {}, []

    def save_candles(self, rows):
        for r in rows:
            self.rows[(r["source"], r["ticker"], r["ts"])] = r
        return len(rows)

    def save_log(self, log):
        self._logs.append(log)

    def candles(self, source, ticker, limit=150):
        rs = [r for r in self.rows.values() if r["source"] == source and r["ticker"] == ticker]
        return sorted(rs, key=lambda r: r["ts"])[-limit:]

    def logs(self, limit=20):
        return list(reversed(self._logs))[:limit]


def get_store():
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    return SupabaseStore(url, key) if url and key else MemoryStore()
