import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

MAX_PROMPT_CHARS = 4000
MAX_FILE_BYTES = 10 * 1024 * 1024
GUEST_MSG_LIMIT = 15
SIGNED_IN_MSG_LIMIT = 60
MIN_SECONDS_BETWEEN_MSGS = 1.0

DB_PATH = Path(__file__).resolve().parent / "jin_ai_chats.db"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chats (
            chat_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            messages_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def list_user_chats(user_id: str) -> list[dict]:
    conn = _db()
    rows = conn.execute(
        "SELECT chat_id, title, updated_at FROM chats WHERE user_id = ? ORDER BY updated_at DESC LIMIT 30",
        (user_id,),
    ).fetchall()
    conn.close()
    return [{"chat_id": r[0], "title": r[1], "updated_at": r[2]} for r in rows]


def load_chat(user_id: str, chat_id: str) -> list[dict]:
    conn = _db()
    row = conn.execute(
        "SELECT messages_json FROM chats WHERE user_id = ? AND chat_id = ?",
        (user_id, chat_id),
    ).fetchone()
    conn.close()
    if not row:
        return []
    try:
        return json.loads(row[0])
    except Exception:
        return []


def save_chat(user_id: str, chat_id: str, messages: list[dict]) -> None:
    if not messages:
        return
    first_user_msg = next((m["content"] for m in messages if m["role"] == "user"), "New Chat")
    clean_title = first_user_msg.split("*(Attached:")[0].strip()[:36]
    if len(first_user_msg.strip()) > 36:
        clean_title += "..."

    conn = _db()
    conn.execute(
        """
        INSERT INTO chats (chat_id, user_id, title, messages_json, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            title = excluded.title,
            messages_json = excluded.messages_json,
            updated_at = excluded.updated_at
        """,
        (chat_id, user_id, clean_title or "New Chat", json.dumps(messages), time.time()),
    )
    conn.commit()
    conn.close()


def delete_chat(user_id: str, chat_id: str) -> None:
    conn = _db()
    conn.execute("DELETE FROM chats WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
    conn.commit()
    conn.close()


def new_chat_id() -> str:
    return uuid.uuid4().hex[:12]


@st.cache_resource(show_spinner=False)
def _get_cached_client() -> genai.Client | None:
    key = ""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            key = str(st.secrets["GEMINI_API_KEY"]).strip().strip('"').strip("'")
    except Exception:
        pass

    if not key:
        key = os.environ.get("GEMINI_API_KEY", "").strip().strip('"').strip("'")

    if not key:
        base_dir = Path(__file__).resolve().parent
        for file_path in (base_dir / ".streamlit" / "secrets.toml", base_dir / ".env"):
            if file_path.exists():
                for enc in ("utf-8-sig", "utf-16", "latin-1"):
                    try:
                        for line in file_path.read_text(encoding=enc).splitlines():
                            clean = line.strip()
                            if clean.startswith("GEMINI_API_KEY") and "=" in clean:
                                val = clean.split("=", 1)[1].strip().strip('"').strip("'")
                                if val:
                                    key = val
                                    break
                    except Exception:
                        continue
            if key:
                break

    if not key:
        return None
    return genai.Client(api_key=key, http_options={"api_version": "v1beta"})


@st.cache_data(ttl=3600, show_spinner=False)
def _discover_account_flash_models() -> list[str]:
    client = _get_cached_client()
    if client is None:
        return []

    skip = ("embed", "imagen", "veo", "aqa", "tts", "audio", "robotics", "computer-use", "1.0", "1.5")
    flash_models = []
    other_gemini = []

    try:
        for m in client.models.list():
            name = (getattr(m, "name", "") or "").replace("models/", "")
            methods = getattr(m, "supported_generation_methods", None) or []
            if methods and "generateContent" not in methods:
                continue
            low = name.lower()
            if "gemini" not in low or any(s in low for s in skip):
                continue
            if "flash" in low:
                flash_models.append(name)
            elif "pro" not in low:
                other_gemini.append(name)
    except Exception:
        pass

    flash_models.sort(key=lambda x: ("lite" not in x.lower(), "2.0" in x.lower()), reverse=False)
    fallbacks = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3-flash-preview",
        "gemini-2.0-flash",
    ]
    ordered = []
    for m in flash_models + other_gemini + fallbacks:
        if m and m not in ordered:
            ordered.append(m)
    return ordered


def validate_and_rate_limit(prompt: str, doc_bytes: bytes | None, is_signed_in: bool) -> None:
    if not prompt or not prompt.strip():
        raise ValueError("Please enter a message.")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError(f"Message too long (max {MAX_PROMPT_CHARS} characters).")
    if doc_bytes and len(doc_bytes) > MAX_FILE_BYTES:
        raise ValueError("Attached file exceeds the 10 MB limit.")

    now = time.time()
    last_ts = st.session_state.get("last_request_ts", 0.0)
    if now - last_ts < MIN_SECONDS_BETWEEN_MSGS:
        raise RuntimeError("Please wait 1 second between messages.")

    msg_count = st.session_state.get("session_msg_count", 0)
    limit = SIGNED_IN_MSG_LIMIT if is_signed_in else GUEST_MSG_LIMIT
    if msg_count >= limit:
        if not is_signed_in:
            raise RuntimeError(f"Guest limit ({GUEST_MSG_LIMIT} messages) reached. Sign in with Google for higher limits.")
        raise RuntimeError(f"Session limit ({SIGNED_IN_MSG_LIMIT} messages) reached. Click New Chat to continue.")

    st.session_state["last_request_ts"] = now
    st.session_state["session_msg_count"] = msg_count + 1


CREATOR_PROFILE = """
Assistant Name: Jin AI
Creator: Shijin Shanavas () Kerala, India)
Education: B.Sc. Computer Science student at University of Kerala (Graduating 2027)
Career Focus: Data Analyst, Cloud Data Engineer, and AI/ML Developer

Experience:
- Data Analytics Intern at Srishti Innovatives, Technopark Phase 1, Thiruvananthapuram (Python, MySQL, Power BI, Tableau, Excel).
- Event  ATTENDED for technical sessions on Embodied AI, Vision-Language-Action models, and Docker Sandboxes.

Projects Built:
1. Vexo Mart: E-commerce storefront built with React, Next.js, Tailwind CSS, and Firebase Realtime Database.
2. Kerala Travel Platform: Interactive travel dataset and web frontend using React, Tailwind CSS, and Supabase.
3. DIGILECTURE: Academic web project developed for B.Sc. Computer Science coursework.
4. Gaming Leaners: Hardware and gaming optimization blog built on WordPress.
5 . OTHER  PROJECT DETAILES NOT EXPOSED AND ALL 

Technical Skills: Python, MySQL, Scikit-learn, Pandas, Power BI, Tableau, Django, React, Next.js, Git & GitHub.
"""

SYSTEM_INSTRUCTION = f"""
You are Jin AI, a fast, helpful, and safe AI assistant created by Shijin Shanavas.

CORE RULES:
1. Speed & Clarity: Give direct, accurate, well-structured answers immediately without unnecessary filler.
2. Identity & Creator Info: When asked "Who are you?", "What is your name?", "Who created you?", or about Shijin Shanavas, introduce yourself as Jin AI and share Shijin's details below accurately without inventing unlisted facts.
3. Strict Content Exclusion: Refuse any request involving sexually explicit/NSFW content, hate speech, harassment, self-harm, violence, illegal hacking, or private sensitive data (Aadhaar numbers, passwords, bank details). Give a brief, polite refusal.

--- CREATOR PROFILE ---
{CREATOR_PROFILE}
-----------------------
"""

STRICT_SAFETY_SETTINGS = [
    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_LOW_AND_ABOVE"),
    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_LOW_AND_ABOVE"),
    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_LOW_AND_ABOVE"),
    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_LOW_AND_ABOVE"),
]


def train_ml_model(df: pd.DataFrame, target_col: str, filename: str) -> dict:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import train_test_split

    clean_df = df.dropna()
    X = pd.get_dummies(clean_df.drop(columns=[target_col]), drop_first=True)
    y = clean_df[target_col]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    if y.dtype == "object" or y.nunique() <= 10:
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        metric_name = "Accuracy"
    else:
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        metric_name = "R2 Score"

    model.fit(X_train, y_train)
    score = round(float(model.score(X_test, y_test)), 3)
    top_features = pd.Series(model.feature_importances_, index=X.columns).nlargest(5).round(3).to_dict()

    summary = (
        f"Dataset '{filename}' ({len(clean_df)} rows) trained to predict '{target_col}'. "
        f"Test {metric_name}: {score}. Top driving features: {top_features}."
    )
    return {
        "metric_name": metric_name,
        "score": score,
        "top_features": top_features,
        "summary": summary,
    }


def _open_fast_stream(client: genai.Client, model_name: str, contents: list):
    try:
        return client.models.generate_content_stream(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                safety_settings=STRICT_SAFETY_SETTINGS,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
    except Exception as err:
        if "thinking" in str(err).lower():
            return client.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    safety_settings=STRICT_SAFETY_SETTINGS,
                ),
            )
        raise


def stream_reply(
    user_prompt: str,
    chat_history: list,
    doc_bytes: bytes = None,
    doc_mime: str = None,
    ml_summary: str = "",
    is_signed_in: bool = False,
):
    validate_and_rate_limit(user_prompt, doc_bytes, is_signed_in)

    client = _get_cached_client()
    if client is None:
        raise RuntimeError("GEMINI_API_KEY not found in .streamlit/secrets.toml.")

    context_prefix = f"[Active ML Model Context: {ml_summary}]\n" if ml_summary else ""
    final_prompt = f"{context_prefix}{user_prompt}"
    recent_history = chat_history[-6:]

    contents = []
    for msg in recent_history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))

    current_parts = [types.Part.from_text(text=final_prompt)]
    if doc_bytes and doc_mime:
        current_parts.append(types.Part.from_bytes(data=doc_bytes, mime_type=doc_mime))
    contents.append(types.Content(role="user", parts=current_parts))

    discovered = _discover_account_flash_models()
    cached_model = st.session_state.get("fast_gemini_model")
    candidates = [cached_model] + [m for m in discovered if m != cached_model] if cached_model else discovered

    last_error = None
    for model_name in candidates:
        try:
            stream = _open_fast_stream(client, model_name, contents)
            first_chunk = next(stream)
            st.session_state["fast_gemini_model"] = model_name
            if getattr(first_chunk, "text", None):
                yield first_chunk.text
            for chunk in stream:
                piece = getattr(chunk, "text", None)
                if piece:
                    yield piece
            return
        except StopIteration:
            st.session_state["fast_gemini_model"] = model_name
            yield "⚠️ I cannot answer that request because it involves restricted or sensitive content."
            return
        except Exception as err:
            last_error = err
            st.session_state.pop("fast_gemini_model", None)
            if "API_KEY_INVALID" in str(err):
                raise RuntimeError("Invalid GEMINI_API_KEY in .streamlit/secrets.toml.")
            continue

    err_text = str(last_error)
    if "429" in err_text or "RESOURCE_EXHAUSTED" in err_text:
        raise RuntimeError("Free-tier rate limit reached. Wait 15 seconds and send again.")
    raise RuntimeError(f"API Error: {err_text}")