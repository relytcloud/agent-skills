# Extensions on Relyt One

Check what a compute offers before relying on an extension:

```sql
SELECT name, default_version, installed_version
FROM pg_available_extensions
WHERE name IN ('vectors', 'vector', 'pg_trgm', 'citext', 'pgcrypto', 'uuid-ossp', 'postgis');
```

Available: `vectors` (pgvecto.rs), `pg_trgm`, `citext`, `pgcrypto`.
Not available: `vector` (pgvector), `uuid-ossp`, `postgis`.

## Vector search: pgvecto.rs (`vectors`), not pgvector

Relyt One ships **pgvecto.rs**, whose extension is named `vectors`. It is **not pgvector**: `CREATE EXTENSION vector`
fails, and pgvector's index methods (`USING hnsw`, `USING ivfflat`) and its operator classes
`vector_cosine_ops` and `vector_ip_ops` do not exist. The column type is also called `vector(n)` and
the distance operators look the same, so most table definitions and queries carry over; indexes and setup do not.

Official documentation: [overview](https://docs.vectorchord.ai/getting-started/overview.html),
[indexing](https://docs.vectorchord.ai/usage/indexing.html),
[schema reference](https://docs.vectorchord.ai/reference/schema.html). (The pgvecto.rs project recommends its
successor VectorChord for new self-hosted deployments; on Relyt One only pgvecto.rs is available.)

### Setup

The extension is normally already created in every database. Its objects live in the schema `vectors`, so put
that schema on the search path:

```sql
CREATE EXTENSION IF NOT EXISTS vectors;
SET search_path TO "$user", public, vectors;                         -- this session
-- ALTER DATABASE mydb SET search_path TO "$user", public, vectors;  -- new sessions (database owner)
```

With a pooled connection, a session-level `SET` does not stick; set the search path on the database or role
instead, or qualify names (`vectors.vector(3)`).

### Table, data, query

```sql
CREATE TABLE items (
  id bigserial PRIMARY KEY,
  content text,
  embedding vector(3) NOT NULL          -- 3 dimensions; use your model's dimension
);

INSERT INTO items (content, embedding) VALUES ('a', '[1,2,3]'), ('b', '[4,5,6]');
-- or from an array: VALUES ('c', ARRAY[1, 2, 3]::real[])

SELECT id, content FROM items ORDER BY embedding <-> '[3,2,1]' LIMIT 5;
```

Operators:

| Operator | Meaning | Operator class for the index |
|---|---|---|
| `<->` | **squared** Euclidean distance (pgvector's `<->` is plain Euclidean; ordering is the same, values differ) | `vector_l2_ops` |
| `<#>` | negative dot product | `vector_dot_ops` |
| `<=>` | cosine distance | `vector_cos_ops` |

### Index

pgvecto.rs has a single index access method, `vectors`. HNSW is the default algorithm; others are chosen with a
TOML `options` string:

```sql
-- default (HNSW), squared Euclidean distance
CREATE INDEX ON items USING vectors (embedding vector_l2_ops);

-- cosine distance
CREATE INDEX ON items USING vectors (embedding vector_cos_ops);

-- IVF instead of HNSW
CREATE INDEX ON items USING vectors (embedding vector_l2_ops)
  WITH (options = $$
[indexing.ivf]
$$);
```

Use the operator that matches the index's operator class in `ORDER BY ... LIMIT`, or the index is not used.

### Porting pgvector code

| pgvector | Relyt One (pgvecto.rs) |
|---|---|
| `CREATE EXTENSION vector;` | `CREATE EXTENSION IF NOT EXISTS vectors;` plus the search path above |
| `USING hnsw (embedding vector_l2_ops)` | `USING vectors (embedding vector_l2_ops)` |
| `USING hnsw (embedding vector_cosine_ops)` | `USING vectors (embedding vector_cos_ops)` |
| `USING ivfflat (embedding vector_l2_ops) WITH (lists = 100)` | `USING vectors (embedding vector_l2_ops) WITH (options = $$ [indexing.ivf] $$)` |
| `SET hnsw.ef_search = ...` | not applicable; see the pgvecto.rs search options documentation |

Libraries and ORM helpers that run `CREATE EXTENSION vector` or create pgvector indexes themselves fail on Relyt
One. Turn that step off (most have an option to skip extension or index creation) and run the SQL above in a
migration.

## UUIDs: `gen_random_uuid()`, not `uuid-ossp`

`gen_random_uuid()` is built into Postgres 13 and later; no extension is needed.

```sql
CREATE TABLE orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now()
);
```

Replace `uuid_generate_v4()` with `gen_random_uuid()` and drop `CREATE EXTENSION "uuid-ossp"` from migrations.

## Other available extensions

```sql
-- fuzzy text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ON items USING gin (content gin_trgm_ops);
SELECT content FROM items WHERE content % 'serch' ORDER BY similarity(content, 'serch') DESC LIMIT 10;

-- case-insensitive text
CREATE EXTENSION IF NOT EXISTS citext;
CREATE TABLE users (email citext UNIQUE NOT NULL);

-- hashing and password digests
CREATE EXTENSION IF NOT EXISTS pgcrypto;
SELECT encode(digest('hello', 'sha256'), 'hex');
```

## No geospatial extension

`postgis` is not available. Store latitude and longitude in `double precision` columns (with a B-tree index for
bounding-box filters) or do geospatial work in the application.
