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
