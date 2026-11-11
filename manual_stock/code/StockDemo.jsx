// Vercel 프론트(React)에 넣는 화면 — 그래프용 데이터만 Railway에 물어본다 (라이브러리 없이 SVG)
import { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL;
const W = 640, H = 300, PAD = 40;

function Chart({ candles }) {
  if (!candles.length) return null;
  const vals = candles.flatMap((c) => [c.close, c.ma5, c.ma20]).filter((v) => v != null);
  const min = Math.min(...vals), max = Math.max(...vals);
  const x = (i) => PAD + (i * (W - PAD * 2)) / Math.max(1, candles.length - 1);
  const y = (v) => H - PAD - ((v - min) / Math.max(1, max - min)) * (H - PAD * 2);
  const line = (key) =>
    candles.map((c, i) => (c[key] == null ? null : `${x(i)},${y(c[key])}`)).filter(Boolean).join(" ");
  const mark = { 골든크로스: "#27ae60", 데드크로스: "#eb5757", 급변동: "#f2994a" };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", background: "#fff", border: "1px solid #ddd" }}>
      <text x={PAD} y={20} fontSize="12">{max.toLocaleString()}원</text>
      <text x={PAD} y={H - 8} fontSize="12">{min.toLocaleString()}원</text>
      <polyline points={line("close")} fill="none" stroke="#0d8784" strokeWidth="2" />
      <polyline points={line("ma5")} fill="none" stroke="#3a82d2" strokeWidth="1.5" strokeDasharray="4 3" />
      <polyline points={line("ma20")} fill="none" stroke="#8e6bc9" strokeWidth="1.5" strokeDasharray="4 3" />
      {candles.map((c, i) =>
        c.signal ? <circle key={i} cx={x(i)} cy={y(c.close)} r="4" fill={mark[c.signal]} /> : null
      )}
    </svg>
  );
}

export default function StockDemo() {
  const [list, setList] = useState([]);
  const [ticker, setTicker] = useState("005930.KS");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      const [l, d] = await Promise.all([
        fetch(`${API}/stocks`).then((r) => r.json()),
        fetch(`${API}/stocks/${ticker}/candles?limit=120`).then((r) => r.json()),
      ]);
      setList(l);
      setData(d);
      setError("");
    } catch (e) {
      setError(String(e));
    }
  }

  // 처음 + 종목을 바꿀 때 + 1분마다 다시 물어보기 (서버는 1시간마다 새 봉을 저장)
  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [ticker]);

  const last = data?.candles?.at(-1);
  return (
    <div style={{ padding: 20, maxWidth: 680 }}>
      <h3>주식 1시간 봉 (yfinance → FastAPI 가공 → Supabase)</h3>
      <p style={{ fontSize: 12, color: "#888" }}>교육용 예제 · 시세는 늦을 수 있음 · 투자 판단용 아님</p>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {list.map((s) => (
          <button key={s.ticker} onClick={() => setTicker(s.ticker)}
            style={{ fontWeight: s.ticker === ticker ? 700 : 400 }}>
            {s.name} {s.ready && <span style={{ color: s.change_pct >= 0 ? "#d8443a" : "#3a82d2" }}>
              {s.change_pct >= 0 ? "▲" : "▼"}{Math.abs(s.change_pct ?? 0)}%</span>}
          </button>
        ))}
      </div>
      {last && (
        <p>
          <b>{data.name}</b> {last.close.toLocaleString()}원 · {last.time} 봉
          {data.mode === "demo" && <small> (연습 데이터)</small>}
        </p>
      )}
      {data?.candles && <Chart candles={data.candles} />}
      <p style={{ fontSize: 12 }}>
        <span style={{ color: "#0d8784" }}>━ 종가</span>{" "}
        <span style={{ color: "#3a82d2" }}>┅ 5시간 평균</span>{" "}
        <span style={{ color: "#8e6bc9" }}>┅ 20시간 평균</span>{" "}
        ● 신호(골든·데드크로스, 급변동)
      </p>
    </div>
  );
}
