-- Supabase → SQL Editor 에 붙여 넣고 Run
create table if not exists candles (
  id          bigint generated always as identity primary key,
  source      text not null,                 -- 'yfinance'(진짜) / 'demo'(연습)
  ticker      text not null,                 -- 005930.KS
  name        text,                          -- 삼성전자
  ts          timestamptz not null,          -- 봉 시작 시각 (1시간 단위)
  open        bigint, high bigint, low bigint, close bigint,
  volume      bigint,
  change_pct  real,                          -- 직전 봉 대비 등락률 %  (FastAPI가 계산)
  ma5         real,                          -- 5시간 이동평균
  ma20        real,                          -- 20시간 이동평균
  signal      text,                          -- 골든크로스 / 데드크로스 / 급변동
  collected_at timestamptz not null default now(),
  unique (source, ticker, ts)                -- 같은 봉은 덮어쓰기 (중복 방지)
);

create table if not exists stock_logs (
  id       bigint generated always as identity primary key,
  ran_at   timestamptz not null default now(),
  source   text,
  tickers  int,      -- 종목 수
  fetched  int,      -- 받은 봉 수
  dropped  int,      -- 버린 봉 수
  cleaned  int,      -- 정리된 봉 수
  saved    int,      -- 저장(덮어쓰기 포함)된 봉 수
  error    text      -- 실패한 종목 메시지
);

-- 브라우저에서 직접 못 건드리게 잠금. FastAPI는 secret 키라서 통과.
alter table candles enable row level security;
alter table stock_logs enable row level security;
