# ConstructAI FastAPI backend

Install the root dependencies with `pip install -r requirements.txt`. Copy `.env.example` to `.env` and set `GROQ_API_KEY` and `GROQ_MODEL`. The backend calls Groq at `https://api.groq.com/openai/v1`. The key is server-side only. Without a key, endpoints use deterministic demo responses where available. Check `/api/health` and backend logs when debugging provider errors.
