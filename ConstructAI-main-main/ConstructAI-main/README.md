# ConstructAI — Multimodal Construction Intelligence Platform

Construction planning and site intelligence tools: safety review, crack assessment, material/cost planning, property valuation, daily site assistance, weather risk guidance, a construction knowledge assistant, and chatbot. Outputs are decision support only and must be verified by qualified professionals.

## Streamlit deployment

1. Push this project to a GitHub repository. Do not commit `.env`, `secrets.toml`, or API keys.
2. In Streamlit Community Cloud, create an app from the repository and set **Main file path** to `streamlit_app.py`.
3. In **App settings → Secrets**, add:

```toml
GROQ_API_KEY = "your-groq-api-key"
GROQ_MODEL = "qwen/qwen3.8-27b"
```

4. Deploy. If no key is configured, deterministic demo responses remain available.

## Run Streamlit locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env` using `backend/.env.example` and set `GROQ_API_KEY` and `GROQ_MODEL`, then run:

```bash
streamlit run streamlit_app.py
```

## Run the original FastAPI web dashboard

```bash
pip install -r requirements.txt
# Configure GROQ_API_KEY in backend/.env
python -m uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000`; API docs are at `/docs`. API keys are read on the server only; the browser does not accept or store them. `GET /api/health` reports whether the Groq SDK and key are configured.

## AI troubleshooting

- This project uses Groq's OpenAI-compatible API at `https://api.groq.com/openai/v1`.
- The default model is `qwen/qwen3.8-27b`; check the Groq Console for current model availability and account limits.
- `ai_ready: true` means the key and SDK are configured; it does not guarantee model access, available quota, or a successful live request.
- Check the backend terminal for detailed provider errors. Common causes include an invalid key, rate limits, unsupported model, or network issues.
- Never put API keys in frontend JavaScript, HTML, or a visible input field.

## API routes

- `POST /api/safety-monitor` — multipart observation, optional image and TXT/DOCX/PDF safety document
- `POST /api/crack-detection` — multipart description and optional image
- `POST /api/project-plan` — JSON project brief and area
- `POST /api/valuation` — JSON property details
- `POST /api/site-assistant` — JSON activity, crew, and conditions
- `POST /api/weather-advisor` — JSON activity and entered weather
- `POST /api/chatbot` — JSON query and optional history
- `POST /api/knowledge` — JSON topic and question; optional TXT/DOCX field guide
- `GET /api/health` — readiness and AI configuration status
