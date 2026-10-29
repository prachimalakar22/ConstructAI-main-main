"""Construction intelligence API. Groq AI is optional; deterministic estimates work offline."""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import zipfile
from xml.etree import ElementTree
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
app = FastAPI(title="ConstructAI", version="1.0.0", description="Construction planning and site intelligence")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class PlanInput(BaseModel):
    brief: str = Field(min_length=3, max_length=2000)
    area_sqft: float = Field(default=1200, gt=0, le=1_000_000)
    location: str = "India"
    quality: str = "Standard"

class ValuationInput(BaseModel):
    location: str = Field(min_length=2, max_length=120)
    area_sqft: float = Field(gt=0, le=1_000_000)
    age_years: float = Field(default=0, ge=0, le=200)
    property_type: str = "Residential"
    amenities: str = ""

class SiteInput(BaseModel):
    activity: str = "Concreting"
    labour_count: int = Field(default=10, ge=0, le=10000)
    site_condition: str = "Normal"

class WeatherInput(BaseModel):
    activity: str = "Slab Concreting"
    weather: str = "Clear"

class ChatInput(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list)

class KnowledgeInput(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    category: str = "Safety"
    generate_document: bool = False
    document_format: str = "txt"

def extract_document(upload: UploadFile) -> str:
    """Read supported safety references with a strict upload and text limit."""
    filename = (upload.filename or "").lower()
    data = upload.file.read(2_000_001)
    upload.file.seek(0)
    if len(data) > 2_000_000:
        raise HTTPException(413, "Safety documents must be 2 MB or smaller.")
    if filename.endswith(".txt"):
        text = data.decode("utf-8-sig", errors="replace")
    elif filename.endswith(".docx"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                root = ElementTree.fromstring(archive.read("word/document.xml"))
            text = " ".join(node.text or "" for node in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
        except Exception as exc:
            raise HTTPException(422, "The DOCX safety document could not be read.") from exc
    elif filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError as exc:
            raise HTTPException(503, "PDF reading requires pypdf. Install backend/requirements.txt and restart.") from exc
        except Exception as exc:
            raise HTTPException(422, "The PDF safety document could not be read.") from exc
    else:
        raise HTTPException(415, "Safety documents must be TXT, DOCX, or PDF files.")
    text = text.strip()
    if not text:
        raise HTTPException(422, "No readable text was found in the safety document.")
    return text[:20_000]

def make_docx(title: str, paragraphs: list[str]) -> bytes:
    """Build a small valid DOCX using the standard library."""
    esc = lambda value: (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    body = f'<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>{esc(title)}</w:t></w:r></w:p>'
    body += "".join(f'<w:p><w:r><w:t xml:space="preserve">{esc(item)}</w:t></w:r></w:p>' for item in paragraphs)
    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return stream.getvalue()

def attach_document(result: dict[str, Any], title: str, generate: bool, fmt: str) -> dict[str, Any]:
    if not generate:
        return result
    if fmt not in {"txt", "docx"}:
        raise HTTPException(422, "Document format must be TXT or DOCX.")
    paragraphs = [result.get("answer", "")] + [f"• {item}" for item in result.get("checklist", [])]
    paragraphs += ["", "Decision support only. Confirm site-specific actions with the responsible professional."]
    if fmt == "docx":
        data, mime, filename = make_docx(title, paragraphs), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "construction_guidance.docx"
    else:
        data, mime, filename = "\n".join([title, "=" * len(title), *paragraphs]).encode("utf-8"), "text/plain; charset=utf-8", "construction_guidance.txt"
    result["document"] = {"filename": filename, "content_type": mime, "content_base64": base64.b64encode(data).decode("ascii")}
    return result

def ai_json(feature: str, inputs: dict[str, Any], image: UploadFile | None = None, api_key: str | None = None) -> dict[str, Any] | None:
    """Call Groq's OpenAI-compatible API. Returns None only when no key is configured."""
    key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
    if not key:
        return None
    model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    try:
        from openai import OpenAI

        content: list[dict[str, Any]] = [{
            "type": "text",
            "text": (
                "You are a cautious construction site decision-support assistant. "
                "Return only a valid JSON object. Do not claim professional certification; "
                "flag uncertainty and recommend qualified inspection when appropriate. "
                + ("For construction_chatbot, include a non-empty string field named 'reply' and an optional 'action_suggestions' list. " if feature == "construction_chatbot" else "")
                + "\\n"
                + json.dumps({"feature": feature, "inputs": inputs}, ensure_ascii=False)
            ),
        }]
        if image is not None:
            raw = image.file.read(20 * 1024 * 1024 + 1)
            image.file.seek(0)
            if len(raw) > 20 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Image must be 20 MB or smaller.")
            mime = image.content_type or "image/jpeg"
            if mime not in {"image/jpeg", "image/png", "image/webp"}:
                raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WebP image.")
            encoded = base64.b64encode(raw).decode("ascii")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}"},
            })
        client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1", timeout=60.0, max_retries=1)
        system_prompt = "Return only a valid JSON object. Be cautious, evidence-based, and transparent about uncertainty."
        if feature == "construction_chatbot":
            system_prompt += " Include a non-empty string field named 'reply' and an optional list named 'action_suggestions'."
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        result = json.loads(response.choices[0].message.content or "{}")
        if not isinstance(result, dict):
            raise ValueError("The model response was not a JSON object.")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Groq request failed for feature %s", feature)
        raise HTTPException(
            status_code=502,
            detail="Groq request failed. Check GROQ_API_KEY, GROQ_MODEL access, account limits, and backend logs.",
        ) from exc

def configured_api_key(request: Request | None = None) -> str | None:
    """Read the Groq credential only from server-side environment/secrets."""
    return os.getenv("GROQ_API_KEY", "").strip() or None


@app.get("/api/health")
def health(request: Request):
    try:
        from openai import OpenAI as _OpenAI  # noqa: F401
        sdk_installed = True
    except ImportError:
        sdk_installed = False
    key_configured = configured_api_key(request) is not None
    return {
        "status": "ok",
        "ai_configured": key_configured,
        "sdk_installed": sdk_installed,
        "ai_ready": key_configured and sdk_installed,
        "provider": "Groq",
        "model": os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
    }

@app.post("/api/safety-monitor")
async def safety_monitor(request: Request, text: str = Form(""), image: UploadFile | None = File(None), document: UploadFile | None = File(None)):
    if image and image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Upload a JPG, PNG, or WebP site photo.")
    document_text = extract_document(document) if document else ""
    ai = ai_json("safety_monitor", {"observation": text, "safety_document_text": document_text}, image, configured_api_key(request))
    if ai:
        return ai
    return {"risk_level": "Review required", "risk_score": 35, "hazards": [{"hazard": "Visual review required", "severity": "Medium", "action": "Have the site safety lead inspect the work area and confirm task-specific controls."}], "ppe": ["Verify hard hats", "Verify high visibility clothing", "Check fall protection where working at height"], "corrective_actions": ["Conduct a toolbox talk before work begins."], "note": "Demo guidance only: configure GROQ_API_KEY on the server to enable AI analysis."}

@app.post("/api/crack-detection")
async def crack_detection(request: Request, description: str = Form(""), image: UploadFile | None = File(None)):
    if not description.strip() and image is None:
        raise HTTPException(422, "Add a description or upload a crack photo.")
    if image and image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Upload a JPG, PNG, or WebP image.")
    ai = ai_json("crack_diagnosis", {"description": description}, image, configured_api_key(request))
    return ai or {"classification": "Requires engineer review", "severity": "Undetermined", "observations": [description or "No textual description supplied."], "possible_causes": ["Cause cannot be determined from incomplete evidence."], "actions": ["Record crack width and length, mark both ends, and monitor for change.", "Request an on-site assessment by a qualified structural engineer."], "note": "Demo guidance only; configure GROQ_API_KEY on the server to enable AI image analysis."}

@app.post("/api/project-plan")
def project_plan(req: PlanInput, request: Request):
    ai = ai_json("project_plan", req.model_dump(), api_key=configured_api_key(request))
    if ai: return ai
    area = req.area_sqft
    rate = {"Economy": 1700, "Standard": 2200, "Premium": 3000}.get(req.quality, 2200)
    cement = round(area * 0.4)
    steel = round(area * 4, 1)
    total = round(area * rate)
    return {"materials": [{"item": "Cement", "quantity": cement, "unit": "bags"}, {"item": "Sand", "quantity": round(area * 0.045, 1), "unit": "tonnes"}, {"item": "Aggregate", "quantity": round(area * 0.09, 1), "unit": "tonnes"}, {"item": "Steel", "quantity": steel, "unit": "kg"}], "costs": {"materials": round(total*.62), "labour": round(total*.28), "finishing": round(total*.10), "total": total, "currency": "INR"}, "schedule": [{"phase": "Site preparation", "duration": "1–2 weeks"}, {"phase": "Foundation and plinth", "duration": "3–5 weeks"}, {"phase": "Structure", "duration": "6–10 weeks"}, {"phase": "Services and finishing", "duration": "6–10 weeks"}], "assumptions": [f"Concept estimate for {area:g} sq ft in {req.location}; actual quantities depend on drawings and specifications.", "Validate with a local quantity surveyor and current supplier rates."]}

@app.post("/api/valuation")
def valuation(req: ValuationInput, request: Request):
    ai = ai_json("property_valuation", req.model_dump(), api_key=configured_api_key(request))
    if ai: return ai
    base_rate = 4500 if req.property_type == "Residential" else 6000
    depreciation = max(.55, 1 - req.age_years * .012)
    value = round(req.area_sqft * base_rate * depreciation)
    return {"estimated_value_inr": value, "range_low_inr": round(value*.88), "range_high_inr": round(value*1.12), "rate_per_sqft_inr": round(value/req.area_sqft), "location": req.location, "basis": "Indicative demonstration estimate; not a live market appraisal.", "factors": ["Location and comparable sales", "Building condition and age", "Amenities and legal status"]}

@app.post("/api/site-assistant")
def site_assistant(req: SiteInput, request: Request):
    ai = ai_json("daily_site_plan", req.model_dump(), api_key=configured_api_key(request))
    return ai or {"tasks": [f"Confirm drawings, permits, and materials for {req.activity.lower()}.", f"Brief the {req.labour_count} available workers and assign a competent supervisor.", "Inspect access, housekeeping, and equipment before starting."], "safety_checks": ["Task-specific PPE", "Toolbox talk and exclusion zones", "Equipment pre-use inspection"], "risk_alerts": [f"Review controls for {req.site_condition.lower()} site conditions."], "materials": ["Confirm approved materials and quantities against the work package."]}

@app.post("/api/weather-advisor")
def weather_advisor(req: WeatherInput, request: Request):
    ai = ai_json("weather_advisory", req.model_dump(), api_key=configured_api_key(request))
    if ai: return ai
    bad = any(w in req.weather.lower() for w in ["heavy rain", "storm", "high wind", "extreme heat"])
    return {"recommendation": "Proceed with caution" if bad else "Proceed with routine checks", "activity": req.activity, "weather": req.weather, "hazards": ["Slippery access and wet electrical equipment"] if bad else ["Conditions may change during the shift"], "precautions": ["Check current site readings and approved method statement.", "Protect fresh concrete and secure loose materials.", "Stop work if manufacturer or site safety limits are exceeded."], "note": "This advisory uses the weather conditions you entered; it is not a live forecast."}

@app.post("/api/chatbot")
def chatbot(req: ChatInput, request: Request):
    ai = ai_json("construction_chatbot", {"query": req.query, "history": req.history[-10:]}, api_key=configured_api_key(request))
    if ai: return ai
    return {"reply": "I can help with construction planning, materials, work sequencing, and site safety. Share the task and conditions for more targeted guidance. Confirm engineering and code decisions with the responsible local professional.", "action_suggestions": ["Create a safety checklist", "Estimate materials", "Review weather risks"]}

@app.post("/api/knowledge")
def knowledge(req: KnowledgeInput, request: Request):
    if req.document_format not in {"txt", "docx"}:
        raise HTTPException(422, "Document format must be TXT or DOCX.")
    ai = ai_json("construction_knowledge", req.model_dump(), api_key=configured_api_key(request))
    result = ai or {"answer": f"For {req.category.lower()} guidance, follow the approved project method statement and applicable local requirements. Confirm site-specific steps with the responsible engineer or safety lead.", "checklist": ["Confirm the current approved drawing or procedure.", "Check training, permits, and required PPE.", "Document inspection results and escalate uncertainty."], "document": None}
    return attach_document(result, f"{req.category.title()} guidance", req.generate_document, req.document_format)

FRONTEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.isdir(FRONTEND):
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
