-- Run in a dedicated Supabase project. No service-role key is required by the Worker.
create table if not exists public.sales_spaces (
 user_id uuid primary key references auth.users(id) on delete cascade,
 data jsonb not null,
 revision bigint not null default 1,
 updated_at timestamptz not null default now(),
 constraint valid_data check (jsonb_typeof(data->'clients')='array' and jsonb_typeof(data->'tasks')='array')
);
alter table public.sales_spaces enable row level security;
revoke all on public.sales_spaces from anon;
grant select,insert,update,delete on public.sales_spaces to authenticated;
create policy own_select on public.sales_spaces for select to authenticated using ((select auth.uid())=user_id);
create policy own_insert on public.sales_spaces for insert to authenticated with check ((select auth.uid())=user_id);
create policy own_update on public.sales_spaces for update to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
create policy own_delete on public.sales_spaces for delete to authenticated using ((select auth.uid())=user_id);
create or replace function public.save_sales_space(incoming jsonb, expected_revision bigint)
returns bigint language plpgsql security invoker set search_path=public as $$
declare next_revision bigint;
begin
 if auth.uid() is null then raise exception 'authentication required'; end if;
 if expected_revision=0 then
  insert into public.sales_spaces(user_id,data,revision) values(auth.uid(),incoming,1)
  on conflict do nothing returning revision into next_revision;
 else
  update public.sales_spaces set data=incoming,revision=revision+1,updated_at=now()
  where user_id=auth.uid() and revision=expected_revision returning revision into next_revision;
 end if;
 if next_revision is null then raise exception 'revision conflict'; end if;
 return next_revision;
end $$;
revoke all on function public.save_sales_space(jsonb,bigint) from public,anon;
grant execute on function public.save_sales_space(jsonb,bigint) to authenticated;
