-- NicheDocs AI — initial schema
-- Run this in the Supabase SQL Editor (Dashboard -> SQL Editor -> New query)
-- or via `supabase db push` if you use the Supabase CLI.

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------

-- pgvector powers similarity search over chunk embeddings.
--
-- Deliberately not schema-qualified: depending on when a Supabase project was
-- created, pgvector may already be installed into `extensions` or into
-- `public`. `if not exists` would silently no-op on the pre-installed case
-- while a hard-coded `extensions.vector(1536)` below would then fail to
-- resolve. Setting the search_path instead makes this migration work on both.
create extension if not exists vector;

set search_path = public, extensions;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

-- One row per uploaded handbook PDF.
create table if not exists public.documents (
    id            uuid primary key default gen_random_uuid(),
    filename      text        not null,
    title         text,
    storage_path  text        not null unique,
    byte_size     bigint      not null default 0,
    page_count    integer     not null default 0,
    chunk_count   integer     not null default 0,
    -- pending   : row created, waiting for the browser to finish its upload
    -- processing: text extraction + embedding in flight
    -- ready     : queryable
    -- failed    : see error_message
    status        text        not null default 'pending'
                  check (status in ('pending', 'processing', 'ready', 'failed')),
    error_message text,
    uploaded_at   timestamptz not null default now(),
    processed_at  timestamptz
);

create index if not exists documents_status_idx
    on public.documents (status);

create index if not exists documents_uploaded_at_idx
    on public.documents (uploaded_at desc);

-- One row per ~600-token slice of a document, with its embedding and the page
-- it came from. `page_number` is what the UI renders as the citation.
create table if not exists public.chunks (
    id           uuid    primary key default gen_random_uuid(),
    document_id  uuid    not null references public.documents (id) on delete cascade,
    chunk_index  integer not null,
    page_number  integer not null,
    -- Last heading seen at or above this chunk, e.g. "4.2 Attendance Policy".
    -- Nullable: not every handbook has detectable headings.
    section      text,
    content      text    not null,
    token_count  integer not null default 0,
    -- text-embedding-3-small emits 1536 dimensions.
    embedding    vector(1536),
    created_at   timestamptz not null default now(),
    unique (document_id, chunk_index)
);

create index if not exists chunks_document_id_idx
    on public.chunks (document_id);

-- HNSW gives better recall/latency than IVFFlat and, unlike IVFFlat, needs no
-- training data to be present before it is built. Cosine distance matches the
-- normalized vectors OpenAI returns.
create index if not exists chunks_embedding_idx
    on public.chunks using hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- Similarity search
-- ---------------------------------------------------------------------------

-- Returns the `match_count` chunks of `p_document_id` most similar to
-- `query_embedding`, best match first. Scoped to a single document on purpose:
-- an answer must never cite a handbook the user did not ask about.
create or replace function public.match_chunks (
    query_embedding vector(1536),
    p_document_id   uuid,
    match_count     integer default 5,
    match_threshold double precision default 0.0
)
returns table (
    id          uuid,
    document_id uuid,
    chunk_index integer,
    page_number integer,
    section     text,
    content     text,
    similarity  double precision
)
language sql
stable
-- Pinned search_path: this function is reachable over PostgREST, so it must not
-- resolve operators through a caller-controlled search_path.
set search_path = public, extensions
as $$
    select
        c.id,
        c.document_id,
        c.chunk_index,
        c.page_number,
        c.section,
        c.content,
        -- <=> is cosine distance in [0, 2]; 1 - distance gives similarity.
        1 - (c.embedding <=> query_embedding) as similarity
    from public.chunks c
    where c.document_id = p_document_id
      and c.embedding is not null
      and 1 - (c.embedding <=> query_embedding) >= match_threshold
    order by c.embedding <=> query_embedding
    limit greatest(match_count, 1);
$$;

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

-- RLS on with zero policies = deny all. The FastAPI backend connects with the
-- service role key, which bypasses RLS; the anon key can therefore read
-- nothing directly. All access is funnelled through the API, which is what we
-- want while there is no per-user auth. When auth is added, replace this with
-- owner-scoped policies rather than loosening it.
alter table public.documents enable row level security;
alter table public.chunks    enable row level security;

revoke all on function public.match_chunks(vector, uuid, integer, double precision)
    from anon;

-- ---------------------------------------------------------------------------
-- Storage
-- ---------------------------------------------------------------------------

-- Private bucket for the original PDFs. Objects are written by the browser via
-- short-lived signed upload URLs and read back only by the backend.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('documents', 'documents', false, 20971520, array['application/pdf'])
on conflict (id) do update
    set public             = excluded.public,
        file_size_limit    = excluded.file_size_limit,
        allowed_mime_types = excluded.allowed_mime_types;
