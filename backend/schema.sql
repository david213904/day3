-- Supabase 대시보드 > SQL Editor 에서 한 번 실행하세요
create table if not exists public.items (
  id bigint generated always as identity primary key,
  name text not null,
  created_at timestamptz not null default now()
);

-- ───── 장바구니 (제주 마켓) ─────
create table if not exists public.cart_items (
  cart_id text not null,
  product_id text not null,
  qty int not null check (qty between 1 and 99),
  created_at timestamptz not null default now(),
  primary key (cart_id, product_id)
);
alter table public.cart_items enable row level security;
alter table public.items enable row level security;
