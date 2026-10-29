"""Streamlit entry point for the ConstructAI construction dashboard."""
from __future__ import annotations

import io
import os
import zipfile
from xml.etree import ElementTree

import streamlit as st
from dotenv import load_dotenv

from backend.main import ai_json, make_docx

load_dotenv()
st.set_page_config(page_title="ConstructAI | Site Intelligence", page_icon="🏗️", layout="wide")

PAGES = [
    "Safety Monitor", "Crack Detection", "Real Estate Valuation", "Project Planner",
    "Knowledge Base", "Chatbot", "Daily Site Assistant", "Weather Advisor",
]

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
:root { --orange:#f47716; --ink:#191a18; --paper:#f1f1ef; }
.stApp { background:var(--paper); color:var(--ink); font-family:'DM Sans',sans-serif; }
[data-testid="stHeader"], footer { visibility:hidden; height:0; }
[data-testid="stToolbar"] { right:1rem; }
[data-testid="stSidebar"] { background:#111210; border-right:1px solid #f47716; }
[data-testid="stSidebar"] > div:first-child { padding:1.2rem .8rem; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:#c7c7c1; }
[data-testid="stSidebar"] [data-testid="stRadio"] label { color:#d9d9d3; font-size:.88rem; padding:.26rem 0; }
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] { gap:.1rem; }
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) { color:#ff9a3d; }
.brand { color:#fff; font:800 1.05rem Manrope,sans-serif; padding:.1rem 0 .9rem; border-bottom:1px solid #30312c; }
.brand span { color:var(--orange); }
.brand small { display:block; margin-top:.3rem; color:#85867f; font:500 .62rem 'DM Sans',sans-serif; letter-spacing:.16em; }
.side-note { position:fixed; bottom:1.5rem; color:#8c8d86; font-size:.68rem; line-height:1.8; }
.page-title { font:800 clamp(1.25rem,2vw,1.8rem) Manrope,sans-serif; letter-spacing:-.035em; text-transform:uppercase; margin:.1rem 0 1.15rem; }
[data-testid="stVerticalBlockBorderWrapper"] { background:#fff; border:1px solid #deded9; border-radius:2px; box-shadow:0 2px 8px #1515100b; }
[data-testid="stVerticalBlockBorderWrapper"] > div { padding:1rem 1.05rem; }
h2, h3 { font-family:Manrope,sans-serif!important; }
h3 { font-size:.95rem!important; text-transform:uppercase; letter-spacing:.01em; }
[data-testid="stWidgetLabel"] p { font-size:.78rem; font-weight:700; color:#464741; }
input, textarea, [data-baseweb="select"] > div { border-radius:2px!important; }
[data-testid="stFileUploader"] section { border:1px dashed #b8b8b2; border-radius:2px; background:#f6f6f4; }
[data-testid="stFileUploader"] section > div { padding:.6rem; }
.stButton > button, .stFormSubmitButton > button, [data-testid="stDownloadButton"] button { border-radius:2px; border:0; background:var(--orange); color:#fff; font-weight:700; text-transform:uppercase; letter-spacing:.04em; min-height:2.35rem; }
.stButton > button:hover, .stFormSubmitButton > button:hover { background:#df6508; color:white; border:0; }
.result-placeholder { min-height:14rem; color:#969791; display:grid; place-items:center; font-style:italic; }
.result-label { color:var(--orange); font:800 .76rem Manrope,sans-serif; text-transform:uppercase; margin-bottom:.4rem; }
.small-muted { color:#85867f; font-size:.75rem; }
@media(max-width:800px) { [data-testid="stSidebar"] { min-width:14rem; } .page-title { margin-top:.2rem; } }
</style>
""", unsafe_allow_html=True)


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
        if value:
            return str(value).strip()
    except Exception:
        pass
    return os.getenv(name, default).strip()


API_KEY = get_secret("GROQ_API_KEY")
MODEL = get_secret("GROQ_MODEL", "qwen/qwen3.8-27b")
os.environ["GROQ_MODEL"] = MODEL
if API_KEY:
    os.environ["GROQ_API_KEY"] = API_KEY

with st.sidebar:
    st.markdown('<div class="brand">🏗 CONSTRUCT<span>AI</span><small>SITE INTELLIGENCE</small></div>', unsafe_allow_html=True)
    st.caption("SITE INTELLIGENCE")
    feature = st.radio("Navigation", PAGES, label_visibility="collapsed")
    st.markdown("<div class='side-note'>● System online<br><br>v1.0.0 ConstructAI</div>", unsafe_allow_html=True)


def ask_ai(name: str, inputs: dict, image_bytes: bytes | None = None, mime: str | None = None):
    if not API_KEY:
        return None
    if image_bytes:
        class BytesUpload:
            def __init__(self, data: bytes, content_type: str):
                self.file = io.BytesIO(data)
                self.content_type = content_type
        return ai_json(name, inputs, image=BytesUpload(image_bytes, mime or "image/jpeg"), api_key=API_KEY)
    return ai_json(name, inputs, api_key=API_KEY)


def title(text: str):
    st.markdown(f'<div class="page-title">{text}</div>', unsafe_allow_html=True)


def render_value(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if child is None or key in {"note", "basis"}:
                continue
            st.markdown(f"**{key.replace('_', ' ').title()}**")
            render_value(child)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                st.markdown(" · ".join(f"{k.replace('_',' ').title()}: {v}" for k, v in item.items()))
            else:
                st.markdown(f"- {item}")
    else:
        st.write(value)


def show_result(result: dict, empty: str = "Your analysis will appear here after you submit the form."):
    if not result:
        st.markdown(f'<div class="result-placeholder">{empty}</div>', unsafe_allow_html=True)
        return
    st.markdown('<div class="result-label">Analysis result</div>', unsafe_allow_html=True)
    render_value(result)
    note = result.get("note") or result.get("basis")
    if note:
        st.caption(note)
    if not API_KEY:
        st.caption("Demo guidance · Add GROQ_API_KEY in Streamlit Secrets to enable AI analysis.")


def call_ai(feature_name: str, inputs: dict, image=None):
    try:
        return ask_ai(feature_name, inputs, image.getvalue() if image else None, image.type if image else None)
    except Exception as exc:
        st.error(f"AI request failed. Check GROQ_API_KEY, GROQ_MODEL access, account limits, and network. Details: {exc}")
        return None


if feature == "Safety Monitor":
    title("Site Safety Monitor")
    left, right = st.columns([1, 1], gap="medium")
    with left:
        with st.container(border=True):
            st.subheader("▣  Input Data")
            with st.form("safety"):
                observation = st.text_area("Observation log", placeholder="Describe the scene e.g. Workers on scaffold without harness...", height=110)
                photo = st.file_uploader("Site photo (optional)", type=["jpg", "jpeg", "png", "webp"])
                doc = st.file_uploader("Safety doc (optional)", type=["txt", "docx", "pdf"])
                submitted = st.form_submit_button("Analyze hazards", use_container_width=True)
    with right:
        with st.container(border=True):
            st.subheader("Analysis Results")
            result = None
            if submitted:
                document_text = ""
                if doc:
                    data = doc.getvalue()
                    if len(data) > 2_000_000:
                        st.error("Safety documents must be 2 MB or smaller.")
                    else:
                        try:
                            if doc.name.lower().endswith(".txt"):
                                document_text = data.decode("utf-8-sig", errors="replace")[:20000]
                            elif doc.name.lower().endswith(".pdf"):
                                from pypdf import PdfReader
                                document_text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)[:20000]
                            else:
                                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                                    root = ElementTree.fromstring(archive.read("word/document.xml"))
                                document_text = " ".join(node.text or "" for node in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))[:20000]
                        except Exception as exc:
                            st.warning(f"Could not read safety document: {exc}")
                result = call_ai("safety_monitor", {"observation": observation, "safety_document_text": document_text}, photo)
                result = result or {"risk_level": "Review required", "risk_score": 35, "hazards": [{"hazard": "Visual review required", "severity": "Medium", "action": "Ask the site safety lead to inspect and confirm task-specific controls."}], "ppe": ["Verify hard hats and high-visibility clothing", "Check fall protection where relevant"], "corrective_actions": ["Conduct a toolbox talk before work begins."], "note": "Demo guidance only; confirm findings on site."}
            show_result(result)

elif feature == "Crack Detection":
    title("Structural Crack Diagnosis")
    with st.container(border=True):
        st.subheader("Input Analysis Data")
        with st.form("cracks"):
            description = st.text_area("Description", placeholder="Describe the crack location and pattern...", height=90)
            photo = st.file_uploader("Crack image", type=["jpg", "jpeg", "png", "webp"])
            submitted = st.form_submit_button("Run diagnosis", use_container_width=True)
        if submitted:
            result = call_ai("crack_diagnosis", {"description": description}, photo)
            show_result(result or {"classification": "Requires engineer review", "severity": "Undetermined", "observations": [description or "No description supplied"], "possible_causes": ["Cause cannot be determined from incomplete evidence"], "actions": ["Record crack width and length", "Request an on-site assessment by a qualified structural engineer"], "note": "Demo guidance only; confirm findings on site."})

elif feature == "Real Estate Valuation":
    title("Real Estate Estimator")
    with st.container(border=True):
        st.subheader("Property Details")
        with st.form("valuation"):
            location = st.text_input("Location", placeholder="City, neighborhood")
            c1, c2 = st.columns(2)
            area = c1.number_input("Area (sq ft)", min_value=1.0, value=1200.0)
            age = c2.number_input("Age (years)", min_value=0.0, max_value=200.0, value=0.0)
            kind = st.selectbox("Type", ["Residential", "Commercial"])
            amenities = st.text_area("Amenities", placeholder="Pool, Gym, Parking...", height=72)
            submitted = st.form_submit_button("Calculate value", use_container_width=True)
        if submitted:
            result = call_ai("property_valuation", {"location": location or "India", "area_sqft": area, "age_years": age, "property_type": kind, "amenities": amenities})
            if not result:
                value = round(area * (4500 if kind == "Residential" else 6000) * max(.55, 1 - age * .012))
                result = {"estimated_value_inr": value, "range_low_inr": round(value * .88), "range_high_inr": round(value * 1.12), "basis": "Indicative demo estimate; not a live market appraisal.", "factors": ["Location and comparable sales", "Building condition and age", "Amenities and legal status"]}
            show_result(result)

elif feature == "Project Planner":
    title("Construction Project Planner")
    with st.container(border=True):
        st.subheader("Project Brief")
        with st.form("planner"):
            brief = st.text_input("Project brief", placeholder="e.g. Create full plan for 20x30 slab construction...", label_visibility="collapsed")
            c1, c2, c3 = st.columns([1, 1, 1])
            area = c1.number_input("Built-up area (sq ft)", min_value=100.0, value=1200.0)
            location = c2.text_input("Location", "India")
            quality = c3.selectbox("Quality", ["Economy", "Standard", "Premium"])
            submitted = st.form_submit_button("Generate plan", use_container_width=True)
    if submitted:
        result = call_ai("project_plan", {"brief": brief or "Construction project", "area_sqft": area, "location": location, "quality": quality})
        if not result:
            rate = {"Economy": 1700, "Standard": 2200, "Premium": 3000}[quality]
            total = round(area * rate)
            result = {"materials": [{"item": "Cement", "quantity": round(area * .4), "unit": "bags"}, {"item": "Sand", "quantity": round(area * .045, 1), "unit": "tonnes"}, {"item": "Aggregate", "quantity": round(area * .09, 1), "unit": "tonnes"}, {"item": "Steel", "quantity": round(area * 4, 1), "unit": "kg"}], "costs": {"materials": round(total * .62), "labour": round(total * .28), "finishing": round(total * .1), "total": total, "currency": "INR"}, "schedule": [{"phase": "Site preparation", "duration": "1–2 weeks"}, {"phase": "Foundation and plinth", "duration": "3–5 weeks"}, {"phase": "Structure", "duration": "6–10 weeks"}, {"phase": "Services and finishing", "duration": "6–10 weeks"}], "assumptions": [f"Concept estimate for {area:g} sq ft in {location}; validate quantities with a local quantity surveyor."]}
    if "planner_result" not in st.session_state:
        st.session_state.planner_result = None
    if submitted:
        st.session_state.planner_result = result
    r = st.session_state.planner_result
    a, b, c = st.columns([1, 1, 1.15])
    for col, heading, key in [(a, "Material Estimator", "materials"), (b, "Cost Estimator", "costs"), (c, "Time Schedule", "schedule")]:
        with col, st.container(border=True):
            st.subheader(heading)
            if r:
                render_value(r.get(key, []))
            else:
                st.caption("Generate a plan to see estimates.")

elif feature == "Knowledge Base":
    title("Knowledge Assistant")
    with st.container(border=True):
        categories = st.columns(3)
        category = st.selectbox("Reference area", ["Safety", "Technique", "Documentation"], label_visibility="collapsed")
        with st.form("knowledge"):
            query = st.text_area("Construction question", placeholder="e.g. Steps for scaffolding", height=95, label_visibility="collapsed")
            c1, c2 = st.columns([1, 1])
            make_doc = c1.checkbox("Prepare field guide")
            fmt = c2.selectbox("Format", ["TXT", "DOCX"])
            submitted = st.form_submit_button("Ask expert")
        if submitted:
            result = call_ai("construction_knowledge", {"category": category, "query": query, "generate_document": False, "document_format": fmt.lower()})
            result = result or {"answer": f"For {category.lower()} guidance, follow the approved project method statement and applicable local requirements.", "checklist": ["Confirm the current approved drawing or procedure", "Check training, permits, and required PPE", "Document inspection results and escalate uncertainty"]}
            show_result(result)
            if make_doc:
                paragraphs = [result.get("answer", "")] + [f"• {x}" for x in result.get("checklist", [])] + ["Decision support only. Confirm site-specific actions with the responsible professional."]
                if fmt == "DOCX":
                    st.download_button("Download field guide (.docx)", make_docx(f"{category} guidance", paragraphs), file_name="construction_guidance.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                else:
                    st.download_button("Download field guide (.txt)", "\n".join([f"{category} guidance", *paragraphs]), file_name="construction_guidance.txt", mime="text/plain")

elif feature == "Chatbot":
    title("Construction Chatbot")
    chat_key = "constructai_groq_chat_history_v2"
    with st.container(border=True):
        chat_area = st.container()
        with chat_area:
            if not st.session_state.get(chat_key):
                st.chat_message("assistant").write("Hello! How can I assist you with your construction query today?")
            for item in st.session_state.get(chat_key, []):
                with st.chat_message(item["role"]):
                    st.write(item["content"])
        prompt = st.chat_input("Type your question...")
        if prompt:
            history = st.session_state.setdefault(chat_key, [])
            history.append({"role": "user", "content": prompt})
            result = call_ai("construction_chatbot", {"query": prompt, "history": history[-10:]})
            reply = ""
            if isinstance(result, dict):
                for field in ("reply", "answer", "response", "message", "text", "content"):
                    candidate = result.get(field)
                    if isinstance(candidate, str) and candidate.strip():
                        reply = candidate.strip()
                        break
            if not reply:
                reply = "I can help with construction planning, materials, work sequencing, and site safety. Share the task and conditions for more targeted guidance. Confirm engineering and code decisions with a responsible local professional."
            history.append({"role": "assistant", "content": reply})
            st.rerun()

elif feature == "Daily Site Assistant":
    title("Daily Site Assistant")
    left, right = st.columns([1, 1], gap="medium")
    with left:
        with st.container(border=True):
            st.subheader("Site Input")
            with st.form("daily"):
                activity = st.selectbox("Planned activity", ["Concreting", "Reinforcement", "Masonry", "Excavation", "Scaffolding", "Finishing"])
                workers = st.number_input("Labour count", min_value=0, max_value=10000, value=10)
                condition = st.selectbox("Site condition", ["Normal", "Rainy", "Hot", "Windy", "Restricted access"])
                submitted = st.form_submit_button("Generate today's plan", use_container_width=True)
    with right:
        with st.container(border=True):
            st.subheader("Today's Execution Plan")
            result = None
            if submitted:
                result = call_ai("daily_site_plan", {"activity": activity, "labour_count": workers, "site_condition": condition})
                result = result or {"tasks": [f"Prepare the construction site for {activity.lower()}", "Conduct safety checks on equipment", "Lay down the reinforcement steel", "Pour the concrete mixture", "Finish and cure the concrete"], "safety_checks": ["Wear hard hat and safety shoes", "Eye protection and dust mask", "Regular inspection of equipment"], "risk_alerts": [f"Review controls for {condition.lower()} site conditions", "Risk of labour accidents during work"]}
            show_result(result, "Submit the site details to build today's plan.")

else:
    title("Weather Advisor")
    left, right = st.columns([1, 1], gap="medium")
    with left:
        with st.container(border=True):
            st.subheader("Check Weather Impact")
            with st.form("weather"):
                activity = st.text_input("Planned activity", "Slab Conversion")
                weather = st.selectbox("Current/forecast weather", ["Clear", "Cloudy", "Light Rain", "Heavy Rain", "High Wind", "Storm", "Extreme Heat"])
                submitted = st.form_submit_button("Check feasibility", use_container_width=True)
    with right:
        with st.container(border=True):
            result = None
            if submitted:
                result = call_ai("weather_advisory", {"activity": activity, "weather": weather})
                if not result:
                    bad = any(w in weather.lower() for w in ["heavy rain", "storm", "high wind", "extreme heat"])
                    result = {"recommendation": "Proceed with caution" if bad else "Proceed with routine checks", "summary": f"For {activity.lower()} under {weather.lower()} conditions, maintain site vigilance and prepare for possible delays.", "hazards": ["Reduced visibility", "Potential for scattered showers", "Increased slip risk on wet surfaces"] if bad else ["Conditions may change during the shift"], "precautions": ["Ensure proper lighting on site", "Have a contingency plan for unexpected rain", "Use slip-resistant materials and equipment"], "note": "Uses entered weather, not a live forecast."}
            if result:
                st.markdown(f"<div class='result-label'>{result.get('recommendation','Weather guidance')}</div>", unsafe_allow_html=True)
                if result.get("summary"):
                    st.write(result["summary"])
                if result.get("hazards"):
                    st.markdown("**Hazards**")
                    st.write(" · ".join(result["hazards"]))
                if result.get("precautions"):
                    st.markdown("**Required precautions**")
                    render_value(result["precautions"])
            else:
                st.markdown('<div class="result-placeholder">Weather guidance will appear here.</div>', unsafe_allow_html=True)
