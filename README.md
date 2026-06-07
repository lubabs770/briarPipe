# briarPipe

**be your own newsboy!**

<br>

### briarPipe turns a repo + your own AI provider key into a personal, AI-curated newspaper.
#### You describe your interests once; on a schedule it reads from a source base *it maintains for you*, writes an edition in the voice you choose, and delivers it. 
#### It never aimlessly scrapes the web — a configurable slice of the token budge (default ~1/5) is spent **cultivating** the source base, the rest **curating** from it.
[check out a demo ->](https://lubabs770.github.io/briarPipe/)




<br>

## Quick start

**1. Clone and open the setup form**

```sh
curl -fsSL https://raw.githubusercontent.com/lubabs770/briarPipe/main/install.sh | bash
```

<br>

This clones the repo into `~/briarPipe`, then serves the form on `localhost` and
opens it.

Fill it in, save the result as **`config.yaml`** in that clone, and commit it.

(Prefer editing by hand? Just edit [`config.yaml`](config.yaml) directly — it's the
single, fully-commented config.)

**3. Let it run.** Invoke `python run.py` on whatever schedule you like (cron,
a systemd timer, Docker, …). It publishes only when an edition is due; each one
is written to [`editions/`](editions/) and sent through your chosen delivery
gateway.

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

Everything lives in a single [`config.yaml`](config.yaml) — fully commented. Key
fields: `interests`, `frequency` (daily/weekly/monthly), `token_budget`
(`max_per_run`, `cultivation_fraction`), `bootstrap_sources`, `provider`, `delivery`,
`output`, and `style` (your editor's voice).

## bring your own provider

```yaml
provider:
  name: openai-compatible
  base_url: https://api.openai.com/v1   # or OpenRouter, Groq, Together, Ollama, …
  model: gpt-4o-mini                    # whatever your endpoint serves
  api_key_env: LLM_API_KEY              # env var your key lives in
```


## Secrets

`config.yaml` is safe to commit — **keep secrets out of it.** briarPipe reads the
AI key and SMTP credentials from the **environment**: `LLM_API_KEY` (or whatever
`provider.api_key_env` names), plus `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASS`, `SMTP_FROM`.

```sh
export LLM_API_KEY=sk-...      # or keep them in a gitignored .env
python run.py
```

For a quick local-only setup you *may* uncomment the `secrets:` block at the
bottom of `config.yaml` and fill it in — but then don't commit that file. Either
way **the environment always wins**, so values set as real environment variables
(or Actions secrets) transparently override anything in the file.

## Running anywhere

briarPipe's core is a plain `python run.py` with **no host-specific code**.
Frequency is config-driven, so any host just needs to invoke it on a regular tick:

```sh
python run.py                 # publish if an edition is due
python run.py --force         # publish regardless of schedule
python run.py --store git     # commit results back to the repo
```

- **A laptop / VPS** — `pip install -r requirements.txt && python run.py` from
  cron or a systemd timer.
- **Docker / cron** — `docker build -t briarpipe .` then run it from any scheduler;
  see the [`Dockerfile`](Dockerfile).

State persistence lives behind a small store seam (`local` filesystem by default,
`git` to commit back), so swapping in object storage later is one small module.

## Delivery

A dated Markdown file is always written to `editions/`. Beyond that, pick a gateway
in `config.yaml` (`delivery.gateway`). **Email** is built in (SMTP via `SMTP_*`
secrets; runs in dry-run mode until configured). The gateway interface is pluggable —
WhatsApp/Telegram/webhooks slot in without touching the pipeline.

## Development

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest
```

## GitHub Actions

Want it to run itself in the cloud? Because secrets come from the environment,
GitHub Actions needs no special config: commit your `config.yaml` with the
sensitive fields left blank, add the keys under **Settings → Secrets and variables
→ Actions** (`LLM_API_KEY`, and `SMTP_*` if you use email), and run
`python run.py --store git` on a schedule so editions commit back to the repo. A
minimal workflow:

```yaml
name: newspaper
on:
  schedule: [{ cron: "0 13 * * *" }]   # daily; run.py decides if an edition is due
  workflow_dispatch:
permissions:
  contents: write                       # to commit editions + state back
jobs:
  curate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - env:
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASS: ${{ secrets.SMTP_PASS }}
          SMTP_FROM: ${{ secrets.SMTP_FROM }}
        run: python run.py --store git
```

## License

MIT
