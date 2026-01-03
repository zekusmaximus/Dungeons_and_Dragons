# Quickstart: Install, Run, and Start Your First Session

This guide gets you from clone to a playable solo session.

## 1) Prerequisites
- Python 3.11+
- Node.js 18+

## 2) Backend setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r service/requirements.txt
```

## 3) Frontend build
```bash
npm --prefix ui install
npm --prefix ui run build
```

## 4) Configure your LLM
Set your provider key and (optional) base URL/model.
```bash
export DM_SERVICE_LLM_API_KEY="your-key"
export DM_SERVICE_LLM_MODEL="gpt-4o"
export DM_SERVICE_LLM_BASE_URL="https://api.openai.com/v1"
```

## 5) Run the combined server
```bash
uvicorn service.app:app --host 0.0.0.0 --port 8000
```

## 6) Start your first session
1. Open `http://localhost:8000`.
2. Click **Start new adventure**.
3. Use the Character Wizard to create your hero.
4. Pick a hook and begin the opening scene.

## Optional: Sanity check
Run a quick validation pass that indexes rules, checks monsters, and creates a demo session.
```bash
python tools/sanity_check.py
```
