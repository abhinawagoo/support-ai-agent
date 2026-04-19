# Support AI Agent

Streamlit UI + OpenAI tool calling + local docs search + URL fetch + optional [Exa](https://exa.ai) web search.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run streamlit_app.py
```

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
   - Optional monitoring: `DOTTLE_API_KEY`, `DOTTLE_URL` (default `https://dottle-production.up.railway.app/api/v1`), `DOTTLE_AGENT_NAME`, `DOTTLE_USER_ID`, `DOTTLE_USER_EMAIL`
5. **Settings** → **Networking** → **Generate domain** (or attach your own).
6. Redeploy if needed after changing variables.

### Cost and abuse note

A public URL means anyone can use your OpenAI quota. Start with low limits on your OpenAI org, watch usage, and add auth / rate limits later if traffic grows.

### Production checklist (deploy + test)

Use this flow after your GitHub repo is connected to Railway.

**1. Variables (same service as the Streamlit app)**  

Set everything you need for the live app plus Dottle:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY` | Chat |
| `DOTTLE_API_KEY` | Monitoring ingest |
| `DOTTLE_URL` | Optional; defaults to `https://dottle-production.up.railway.app/api/v1` |
| `DOTTLE_AGENT_NAME`, `DOTTLE_USER_ID`, `DOTTLE_USER_EMAIL` | Optional session labels |

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
