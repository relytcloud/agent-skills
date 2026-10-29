# Relyt One agent skills

[Agent Skills](https://agentskills.io) that teach coding agents (Claude Code, Codex, Cursor and others) how to
work with [Relyt One](https://relytone.data.cloud), a serverless Postgres service.

| Skill | Use it for |
|---|---|
| [`relyt-one`](skills/relyt-one/SKILL.md) | Projects, branches and computes; connection strings (direct and pooled); the Open API with API keys; extensions (pgvecto.rs vector search, `gen_random_uuid()`, `pg_trgm`); row-level security and the `BYPASSRLS` pitfall |
| [`relyt-managed-auth`](skills/relyt-managed-auth/SKILL.md) | Managed auth (**Preview**): trusted origins and callback URLs, JWT verification with [`@relyt/auth`](https://github.com/relytcloud/relyt-auth-js), Next.js middleware, RLS with the JWT subject, teams and permissions, social sign-in, troubleshooting |

The skills describe only what exists today. See [Roadmap / not yet available](#roadmap--not-yet-available).

## Install

### Claude Code (plugin marketplace)

```text
/plugin marketplace add relytcloud/agent-skills
/plugin install relyt-one@relyt
```

or from a shell: `claude plugin marketplace add relytcloud/agent-skills` and
`claude plugin install relyt-one@relyt`. The skills then load automatically when relevant, or run them as
`/relyt-one:relyt-one` and `/relyt-one:relyt-managed-auth`.

### skills.sh (any agent supported by the `skills` CLI)

```bash
npx skills add relytcloud/agent-skills
```

### Manual copy

Copy the skill directories you want into the skills directory your agent reads:

| Agent | Project | User (all projects) |
|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Codex | `.agents/skills/` | `~/.agents/skills/` |
| Cursor | `.cursor/skills/` or `.agents/skills/` (also reads `.claude/skills/`) | `~/.cursor/skills/` |

```bash
git clone https://github.com/relytcloud/agent-skills.git
mkdir -p .agents/skills && cp -R agent-skills/skills/relyt-one agent-skills/skills/relyt-managed-auth .agents/skills/
```

Agents without skill support can read [llms.txt](llms.txt) and the `SKILL.md` files as plain documentation.

## Roadmap / not yet available

These do **not** exist yet. Agents must not call, install or invent them:

- a Relyt One MCP server;
- a Relyt One CLI;
- a Data API (REST or GraphQL over your database);
- migration tooling from Neon or other Postgres providers;
- the `vector` (pgvector), `uuid-ossp` and `postgis` extensions (use `vectors` / pgvecto.rs and
  `gen_random_uuid()`; there is no geospatial extension).

Managed auth is in **Preview**: behaviour and console settings can still change.

## Repository layout

```
skills/<name>/SKILL.md        one directory per skill (Agent Skills format)
skills/<name>/references/     details loaded on demand
.claude-plugin/               Claude Code plugin (plugin.json) and marketplace (marketplace.json)
scripts/                      CI checks (frontmatter, links, API paths, hygiene scan)
llms.txt                      index for LLMs
```

## Development

```bash
pip install pyyaml
python3 scripts/check_skills.py      # SKILL.md frontmatter (Agent Skills spec)
python3 scripts/check_links.py       # relative links resolve, external links are well-formed
python3 scripts/check_api_paths.py   # curl examples use only documented Open API paths and parameters
python3 scripts/scan.py              # no internal hosts, credentials or non-English text (files and history)
claude plugin validate .             # if Claude Code is installed
```

Contributions: keep skills factual (only features that exist), English only, no credentials or real host names
beyond the public service URL, and keep each `SKILL.md` under 500 lines.

## License

[MIT](LICENSE)
