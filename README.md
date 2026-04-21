# Support AI Agent

Streamlit UI + OpenAI/Anthropic tool calling: **simulated CRM + Google Drive**, local docs, URL fetch, optional [Exa](https://exa.ai). Sidebar scenarios and **failure simulation** help exercise [Dottle](https://dottle-production.up.railway.app) like production agents (ok + error tool spans).

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run streamlit_app.py
```

The Streamlit sidebar includes **demo scenarios**: simulated **CRM**, **Google Drive**, **internal docs**, URL fetch, optional **Exa**, multi-tool chains, and **forced failures** so Dottle captures realistic ok/error spans like production agents.

## Test Dottle (monitoring scenarios)

This repo includes a small **scenario runner** that hits the same ingest paths as production (`/api/v1/ingest/...`) so you can validate sessions, LLM spans, tool spans (ok + error), and session end (completed vs error) in the Dottle dashboard.

```bash
pip install -r requirements-dev.txt
export DOTTLE_API_KEY=dtl_live_...
# optional: export DOTTLE_URL=https://dottle-production.up.railway.app/api/v1

python scripts/run_dottle_scenarios.py
```

Or with pytest (skipped if `DOTTLE_API_KEY` is unset):

```bash
pytest tests/test_dottle_platform.py -m integration -v
```

Scenarios live in `tests/dottle_platform/scenarios.py` — add new functions and append them to `SCENARIOS`.

**Note:** `DOTTLE_TEST_SYNC=1` is set by the runner so HTTP completes before the process exits (production agents still use background threads).

## Deploy on Railway (public URL)

1. Push this repo to GitHub (see below).
2. In [Railway](https://railway.app): **New Project** → **Deploy from GitHub repo** → pick this repository.
3. Railway will detect **Nixpacks** from `requirements.txt` and use `railway.toml` / `Procfile` for the start command (Streamlit binds to `$PORT` on `0.0.0.0`).
4. Open the service → **Variables** → add at least one LLM key:
  - `OPENAI_API_KEY` — for OpenAI models
  - `ANTHROPIC_API_KEY` — for Anthropic Claude models
  - Optional: `EXA_API_KEY` (Exa search tool), `OPENAI_MODEL`, `ANTHROPIC_MODEL`, `LLM_PROVIDER` (`openai` or `anthropic`, default `openai`)
  - Optional monitoring: `DOTTLE_API_KEY`, `DOTTLE_URL` (default `https://dottle-production.up.railway.app/api/v1`), `DOTTLE_AGENT_NAME`, `DOTTLE_USER_ID`, `DOTTLE_USER_EMAIL`, `DOTTLE_AGENT_VERSION`, `DOTTLE_TAGS`, `DOTTLE_REDACT_PII`
5. **Settings** → **Networking** → **Generate domain** (or attach your own).
6. Redeploy if needed after changing variables.

### Cost and abuse note

A public URL means anyone can use your OpenAI quota. Start with low limits on your OpenAI org, watch usage, and add auth / rate limits later if traffic grows.

### Production checklist (deploy + test)

Use this flow after your GitHub repo is connected to Railway.

**1. Variables (same service as the Streamlit app)**  

Set everything you need for the live app plus Dottle:


| Variable                                                   | Purpose                                                                 |
| ---------------------------------------------------------- | ----------------------------------------------------------------------- |
| `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY`                | Chat                                                                    |
| `DOTTLE_API_KEY`                                           | Monitoring ingest                                                       |
| `DOTTLE_URL`                                               | Optional; defaults to `https://dottle-production.up.railway.app/api/v1` |
| `DOTTLE_AGENT_NAME`, `DOTTLE_USER_ID`, `DOTTLE_USER_EMAIL` | Optional session labels                                                 |
| `DOTTLE_AGENT_VERSION`, `DOTTLE_TAGS`                        | Optional release/version grouping + comma-separated tags                |
| `DOTTLE_REDACT_PII`                                           | Optional (`true/1`) to mask common PII/API-key patterns before ingest  |


Redeploy after saving variables (**Deployments** → **Redeploy**), or trigger a deploy by pushing to `main`.

**2. Smoke-test the deployed UI**  

Open **Networking → your Railway URL**, pick a provider/model in the sidebar, send one chat message. Confirm the assistant replies and Dottle shows a session/spans.

**3. Run Dottle scenario tests using production secrets (recommended)**  

Railway’s runtime image only installs `requirements.txt` (not dev deps). Easiest approach: run the scenario runner **on your machine** while Railway **injects the same env vars** as production:

```bash
# One-time: https://docs.railway.app/develop/cli — then:
cd /path/to/support-ai-agent
railway login
railway link          # select this project/service

pip install -r requirements-dev.txt
railway run python scripts/run_dottle_scenarios.py
```

That uses your **Railway Variables** for `DOTTLE_API_KEY` etc., so ingest hits Dottle the same way the deployed app does. Expect all scenarios to print `ok`.

**4. Optional: pytest with Railway env**

```bash
railway run pytest tests/test_dottle_platform.py -m integration -v
```

(`pytest` must be installed locally via `requirements-dev.txt`.)

## Telegram + Supabase + Google + Slack workflow bot

This repo now includes a terminal bot script at `scripts/telegram_ops_bot.py` that:

- listens to Telegram messages (long polling),
- does web discovery with Exa (`EXA_API_KEY`) for any query, with URL fetch fallback,
- reads context from Google Docs,
- stores each generated report row in Supabase,
- appends the same row to Google Sheets and local Excel (`.xlsx`),
- sends report updates to Telegram and optional Slack.

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Configure env vars

Copy `.env.example` to `.env` and set:

- Telegram: `TELEGRAM_BOT_TOKEN` (+ optional `TELEGRAM_CHAT_ID`)
- Web browsing: `EXA_API_KEY` (recommended)
- Supabase: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, optional `SUPABASE_TABLE`
- Google: `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_DOC_ID`, `GOOGLE_SHEET_ID`, optional `GOOGLE_SHEET_NAME`
- Excel path: `EXCEL_FILE_PATH`
- Slack (optional): `SLACK_WEBHOOK_URL`

### 3) Create Supabase table (example)

```sql
create table if not exists public.agent_reports (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  chat_id text,
  instruction text,
  source_url text,
  report text
);
```

### 4) Run bot from terminal

```bash
python scripts/telegram_ops_bot.py
```

Send your bot a message like:

`check https://status.openai.com and prepare incident summary for leadership`

The bot will process, store, and send report updates.

### Telegram command modes

- `/quick <query>`: faster Exa pass (fewer results, lower token/cost footprint)
- `/deep <query>`: broader Exa pass (more results for richer summaries)
- `/status`: show whether key integrations are configured
- `/help`: show command help in chat
- `<query>` without command: normal mode

## Push to GitHub

```bash
cd /path/to/support-ai-agent
git add -A
git commit -m "Initial support agent with Railway deploy config"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

Replace `<you>` / `<repo>` with your GitHub user and repository name.