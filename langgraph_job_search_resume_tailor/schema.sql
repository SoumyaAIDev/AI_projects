create extension if not exists pgcrypto;

create table if not exists public.jobs (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    company text not null,
    url text not null unique,
    full_jd text not null,
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_jobs_created_at on public.jobs (created_at desc);
create index if not exists idx_jobs_title_company on public.jobs (title, company);
