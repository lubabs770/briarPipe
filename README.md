# briarPipe

**be your own newsboy!**

briarPipe turns a repo + your own AI provider key into a personal, AI-curated
newspaper. You describe your interests once; on a schedule it reads from a source
base *it maintains for you*, writes an edition in the voice you choose, and delivers
it. It never aimlessly scrapes the web — a configurable slice of the token budget
(default ~1/5) is spent **cultivating** the source base, the rest **curating** from it.

---

## Quick start

**1. Get the setup form** (no clone, no YAML knowledge needed):

```sh
curl -fsSL https://raw.githubusercontent.com/lubabs770/briarPipe/main/install.sh | bash
```

This serves the form on `localhost` and opens it. Fill it in, then save the result
as **`config.yml`** in your fork and commit it. (Prefer editing by hand? Copy
[`config.example.yml`](config.example.yml) to `config.yml`.)

**2. Add your AI key** as a secret. On GitHub:
*Settings → Secrets and variables → Actions →* `ANTHROPIC_API_KEY`.
Keys live in secrets/env vars only — **never** in `config.yml`.

**3. Let it run.** The included GitHub Actions workflow runs daily and publishes
when an edition is due. Each edition is committed to [`editions/`](editions/) and
sent through your chosen delivery gateway.

---

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
