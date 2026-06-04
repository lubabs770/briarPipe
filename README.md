# briarPipe

**be your own newsboy!**

<br>

### briarPipe turns a repo + your own AI provider key into a personal, AI-curated newspaper.
### You describe your interests once; on a schedule it reads from a source base *it maintains for you*, writes an edition in the voice you choose, and delivers it. 
### It never aimlessly scrapes the web — a configurable slice of the token budge (default ~1/5) is spent **cultivating** the source base, the rest **curating** from it.
[check out a demo ->](https://lubabs770.github.io/briarPipe/)




<br>

## Quick start

**1. Clone and open the setup form** (no YAML knowledge needed):

```sh
curl -fsSL https://raw.githubusercontent.com/lubabs770/briarPipe/main/install.sh | bash
```

<br>

This clones the repo into `~/briarPipe`, then serves the form on `localhost` and
opens it. Fill it in, save the result as **`config.yml`** in that clone, and commit
it. (Prefer editing by hand? Copy [`config.example.yml`](config.example.yml) to
`config.yml`.)

**2. Add your AI key.** Two ways (see [Secrets](#secrets) for the trade-off):
- **Local / cron / Docker:** drop it in the `secrets:` block of `config.yml` (the
  form has fields for it). `config.yml` is gitignored, so it stays off GitHub.
- **GitHub Actions:** add it as an Actions secret —
  *Settings → Secrets and variables → Actions →* `ANTHROPIC_API_KEY` — and keep
  `secrets:` out of the committed file.

**3. Let it run.** The included GitHub Actions workflow runs daily and publishes
when an edition is due. Each edition is committed to [`editions/`](editions/) and
sent through your chosen delivery gateway.

<br>

## How it works

Each run is six steps, the middle two bounded by your token budget:

1. **Load** your config, the source base (`state/sources.json`) and the continuity
   memory (`STATE.md`).
2. **Bootstrap** (first run only) — discover feeds from your seed URLs. No tokens.
3. **Fetch** recent stories from known feeds. No tokens.
4. **Curate (~80%)** — the AI picks what matters, writes the edition in your style,
   *and* refreshes `STATE.md` in the same call so continuity is free.
5. **Cultivate (~20%)** — the AI proposes a few new sources and prunes dead ones;
   new feeds are validated before joining the base. Bounded discovery, never crawling.
6. **Render, persist, deliver** — write the Markdown edition, save state, send it,
   commit everything back.

**`STATE.md`** is a terse running memory of what's already been covered. It's fed
into every edition so the paper *advances* instead of repeating — you learn a field a
little at a time.

## Configuration

See [`config.example.yml`](config.example.yml) for the full, commented schema. Key
fields: `interests`, `frequency` (daily/weekly/monthly), `token_budget`
(`max_per_run`, `cultivation_fraction`), `bootstrap_sources`, `provider`, `delivery`,
`output`, and `style` (your editor's voice).

## Secrets

briarPipe reads secrets (the AI key, SMTP credentials) from **environment
variables** — `ANTHROPIC_API_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASS`, `SMTP_FROM`. For convenience you can instead keep them in a `secrets:`
block right in `config.yml`:

```yaml
secrets:
  anthropic_api_key: sk-ant-...     # -> ANTHROPIC_API_KEY
  smtp_host: smtp.example.com
  smtp_user: you@example.com
  smtp_password: app-password
```

Two rules make this safe:

- **The environment always wins.** Values in `secrets:` are only used when the
  matching variable is unset — so Actions secrets transparently override the file.
- **A file with real secrets is never committed.** `config.yml` is **gitignored by
  default** for exactly this reason; `config.example.yml` is the committed template.

**Pick your path:**

| Host | What to do |
| --- | --- |
| Laptop / cron / Docker | Fill in `secrets:` (the form has fields). Never push `config.yml`. |
| **GitHub Actions** | 1) Set keys as **Actions secrets**, not in the file. 2) Leave `secrets:` out of `config.yml`. 3) Commit the keyless config explicitly: `git add -f config.yml` (it's gitignored). |

Either way, **do not put real keys in a file you then commit to a public repo.**

## Running anywhere

briarPipe's core is a plain `python run.py` with **no host-specific code** — GitHub
Actions is just one adapter. Frequency is config-driven, so any host just needs to
invoke it on a regular tick:

```sh
python run.py                 # publish if an edition is due
python run.py --force         # publish regardless of schedule
python run.py --store git     # commit results back (used in CI)
```

- **GitHub Actions** — included at [`.github/workflows/newspaper.yml`](.github/workflows/newspaper.yml).
- **Docker / cron** — `docker build -t briarpipe .` then run it from any scheduler;
  see the [`Dockerfile`](Dockerfile).
- **A laptop / VPS** — `pip install -r requirements.txt && python run.py`.

State persistence lives behind a small store seam (`local` filesystem by default,
`git` to commit back), so swapping in object storage later is one small module.

## Delivery

A dated Markdown file is always written to `editions/`. Beyond that, pick a gateway
in `config.yml` (`delivery.gateway`). **Email** is built in (SMTP via `SMTP_*`
secrets; runs in dry-run mode until configured). The gateway interface is pluggable —
WhatsApp/Telegram/webhooks slot in without touching the pipeline.

## Development

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest
```

## License

MIT
