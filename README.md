# AI Interview Preparation System

A Flask + SQLite mock interview web application for Windows 11. It includes registration/login, a seeded question bank, answer evaluation, feedback, reports, and interview history.

## Requirements
- Windows 11
- Python 3.10 or newer
- VS Code (recommended)
- Optional: an API key for an OpenAI-compatible AI service

## 1. Open the project
Extract the ZIP, then open the `ai_interview_system` folder in VS Code.

## 2. Create a virtual environment
In the VS Code terminal (PowerShell):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt and run:
```bat
.venv\Scripts\activate.bat
```

## 3. Install packages
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configure environment variables
Copy `.env.example` to `.env` in the project root. In PowerShell:

```powershell
Copy-Item .env.example .env
```

Open `.env` and set `FLASK_SECRET_KEY` to a long random value. For AI evaluation, add your provider's API key to `OPENAI_API_KEY`. Keep `.env private; never upload it to GitHub.

If you leave `OPENAI_API_KEY` blank, the app still works using a simple keyword-based fallback. This fallback is only a rough estimate, not a true semantic AI evaluation.

## 5. Run the app
```powershell
python app.py
```
Open the local address shown in the terminal, usually `http://127.0.0.1:5000`.

Stop the server with `Ctrl+C`.

## 6. Try the app
1. Register an account.
2. Log in.
3. Choose a category and target role on the dashboard.
4. Answer each question and review the feedback.
5. Finish the interview to see the report.
6. Open History to view prior sessions.

## How the AI integration works
`services/ai_service.py` uses an OpenAI-compatible Chat Completions API when `OPENAI_API_KEY` is configured. `OPENAI_MODEL` controls the model. `OPENAI_BASE_URL` can be set for compatible providers. If the AI request fails, a local fallback prevents the interview from crashing.

API use may incur charges and is subject to the provider's terms. Do not submit sensitive personal information or real confidential interview data.

## Project structure
- `app.py`: Flask routes and database initialization
- `services/ai_service.py`: AI integration and fallback evaluation
- `services/scoring.py`: overall score calculation
- `templates/`: HTML pages
- `static/css/style.css`: application styles
- `static/js/interview.js`: small interview UI helpers
- `instance/interview.db`: created automatically on first run

## Important production improvements
This is a learning project, not a production-ready service. Before public deployment, add CSRF protection, rate limiting, email verification/password reset, stronger logging/monitoring, database backups, and a production WSGI server. Use HTTPS and set a secure session cookie configuration.
