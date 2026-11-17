import base64
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import backend

# Custom Jin AI SVG Logo encoded as Data URI (works everywhere without external files)
JIN_LOGO_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0F172A"/>
      <stop offset="100%" stop-color="#1E1B4B"/>
    </linearGradient>
    <linearGradient id="glow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#60A5FA"/>
      <stop offset="50%" stop-color="#A78BFA"/>
      <stop offset="100%" stop-color="#F472B6"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="112" fill="url(#bg)"/>
  <circle cx="256" cy="220" r="135" fill="url(#glow)" opacity="0.22"/>
  <text x="256" y="275" font-size="210" text-anchor="middle" dominant-baseline="middle">🧞</text>
  <text x="256" y="425" font-family="Arial, sans-serif" font-weight="bold" font-size="64" fill="#F8FAFC" text-anchor="middle">JIN AI</text>
</svg>
""".strip()

JIN_LOGO_DATA_URI = "data:image/svg+xml;base64," + base64.b64encode(JIN_LOGO_SVG.encode("utf-8")).decode("utf-8")

st.set_page_config(
    page_title="Jin AI",
    page_icon=JIN_LOGO_DATA_URI,
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ==============================================================================
# 1. OVERRIDE BROWSER & PHONE HOME-SCREEN ICON + MANIFEST (Replaces Streamlit Logo)
# ==============================================================================
components.html(
    f"""
    <script>
    (function() {{
        const targets = [window.document];
        try {{
            if (window.parent && window.parent.document) {{
                targets.push(window.parent.document);
            }}
            if (window.top && window.top.document) {{
                targets.push(window.top.document);
            }}
        }} catch (e) {{}}

        // Render SVG onto an HTML5 Canvas to generate a real 512x512 PNG for Android/iOS Home Screen
        const img = new Image();
        img.onload = function() {{
            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 512;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, 512, 512);
            const pngUrl = canvas.toDataURL('image/png');

            const manifestObj = {{
                name: "Jin AI",
                short_name: "Jin AI",
                description: "Jin AI Assistant by Shijin Shanavas",
                start_url: window.location.origin,
                display: "standalone",
                background_color: "#0E1117",
                theme_color: "#0E1117",
                icons: [
                    {{ src: pngUrl, sizes: "192x192", type: "image/png", purpose: "any maskable" }},
                    {{ src: pngUrl, sizes: "512x512", type: "image/png", purpose: "any maskable" }}
                ]
            }};
            const manifestBlob = new Blob([JSON.stringify(manifestObj)], {{ type: 'application/json' }});
            const manifestUrl = URL.createObjectURL(manifestBlob);

            targets.forEach(doc => {{
                try {{
                    doc.title = "Jin AI";
                    // Remove existing Streamlit favicons & manifests
                    doc.querySelectorAll("link[rel*='icon'], link[rel='apple-touch-icon'], link[rel='manifest']").forEach(el => el.remove());

                    const iconLink = doc.createElement('link');
                    iconLink.rel = 'icon';
                    iconLink.type = 'image/png';
                    iconLink.href = pngUrl;
                    doc.head.appendChild(iconLink);

                    const appleLink = doc.createElement('link');
                    appleLink.rel = 'apple-touch-icon';
                    appleLink.href = pngUrl;
                    doc.head.appendChild(appleLink);

                    const manifestLink = doc.createElement('link');
                    manifestLink.rel = 'manifest';
                    manifestLink.href = manifestUrl;
                    doc.head.appendChild(manifestLink);
                }} catch (err) {{}}
            }});
        }};
        img.src = "{JIN_LOGO_DATA_URI}";
    }})();
    </script>
    """,
    height=0,
    width=0,
)

# ==============================================================================
# 2. CLEAN GEMINI / CHATGPT UI CSS
# ==============================================================================
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    .viewerBadge_container__r5tak {display: none !important;}
    header[data-testid="stHeader"] {background: transparent !important;}

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 5.5rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 780px;
    }

    div.stButton > button {
        width: 100%;
        border-radius: 14px;
        border: 1px solid #262C36;
        background-color: #161B22;
        color: #E6EDF3;
        padding: 0.78rem 1rem;
        text-align: left;
        font-size: 0.9rem;
        line-height: 1.35;
        transition: all 0.18s ease;
    }
    div.stButton > button:hover {
        border-color: #60A5FA;
        background-color: #1C2331;
        transform: translateY(-1px);
    }

    [data-testid="stChatMessage"] {
        border-radius: 18px;
        padding: 0.85rem 1.05rem;
        margin-bottom: 0.65rem;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }

    [data-testid="stChatInput"] {
        border-radius: 24px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _oauth_ready() -> bool:
    try:
        return "auth" in st.secrets and "google" in st.secrets["auth"]
    except Exception:
        return False


def _user_logged_in() -> bool:
    if not _oauth_ready():
        return False
    try:
        return bool(getattr(st.user, "is_logged_in", False))
    except Exception:
        return False


def _current_user_id() -> str:
    if _user_logged_in():
        email = st.user.get("email")
        if email:
            return email.lower().strip()
    if "guest_uid" not in st.session_state:
        st.session_state.guest_uid = f"guest_{backend.new_chat_id()}"
    return st.session_state.guest_uid


if "active_chat_id" not in st.session_state:
    st.session_state.active_chat_id = backend.new_chat_id()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "ml_summary" not in st.session_state:
    st.session_state.ml_summary = ""

user_id = _current_user_id()

# ==============================================================================
# 3. COLLAPSIBLE SIDEBAR
# ==============================================================================
with st.sidebar:
    st.markdown("### 🧞 Jin AI")

    if st.button("＋ New Chat", key="new_chat_btn"):
        st.session_state.active_chat_id = backend.new_chat_id()
        st.session_state.messages = []
        st.session_state.ml_summary = ""
        st.session_state.pending_prompt = None
        st.rerun()

    saved_chats = backend.list_user_chats(user_id)
    if saved_chats:
        st.markdown("---")
        st.caption("RECENT CHATS")
        for chat in saved_chats:
            cid = chat["chat_id"]
            is_active = cid == st.session_state.active_chat_id
            label = f"💬 {chat['title']}" if is_active else chat["title"]

            c_open, c_del = st.columns([5, 1])
            with c_open:
                if st.button(label, key=f"open_{cid}"):
                    st.session_state.active_chat_id = cid
                    st.session_state.messages = backend.load_chat(user_id, cid)
                    st.session_state.pending_prompt = None
                    st.rerun()
            with c_del:
                if st.button("🗑️", key=f"del_{cid}", help="Delete chat"):
                    backend.delete_chat(user_id, cid)
                    if is_active:
                        st.session_state.active_chat_id = backend.new_chat_id()
                        st.session_state.messages = []
                    st.rerun()

    st.markdown("---")
    st.markdown("**📎 Attach Image or PDF**")
    uploaded_doc = st.file_uploader(
        "Upload notes, screenshots, or PDFs",
        type=["pdf", "png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("**📊 ML Data Analyzer (CSV)**")
    csv_file = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")
    if csv_file is not None:
        df = pd.read_csv(csv_file)
        st.caption(f"{len(df)} rows × {len(df.columns)} columns")
        target_col = st.selectbox("Target column", df.columns)
        if st.button("Train ML Model", key="train_ml_btn"):
            with st.spinner("Training model..."):
                res = backend.train_ml_model(df, target_col, csv_file.name)
                st.session_state.ml_summary = res["summary"]
                st.success(f"{res['metric_name']}: {res['score']}")

    if st.session_state.ml_summary:
        st.info("ML model active for this chat.")

    st.markdown("---")
    if _user_logged_in():
        p_col1, p_col2 = st.columns([1, 3])
        with p_col1:
            if st.user.get("picture"):
                st.image(st.user.get("picture"), width=40)
        with p_col2:
            st.markdown(f"**{st.user.get('name', 'Google User')}**")
            if st.user.get("email"):
                st.caption(st.user.get("email"))
        if st.button("Sign out", key="logout_btn"):
            st.logout()
    else:
        if st.button("🔵 Sign in with Google", key="sidebar_login_btn"):
            if _oauth_ready():
                st.login("google")
            else:
                st.warning("Configure `[auth]` in Streamlit Secrets to enable Google Sign-In.")
        st.caption("Sign in to sync chat history across devices.")

# ==============================================================================
# 4. MAIN CHAT INTERFACE WITH GUARANTEED OPENING JIN-FROM-CANDLE ANIMATION
# ==============================================================================
user_input = st.chat_input("Ask Jin AI anything...")
active_prompt = st.session_state.pending_prompt or user_input
st.session_state.pending_prompt = None

if not st.session_state.messages and not active_prompt:
    first_name = st.user.get("given_name", "") if _user_logged_in() else ""
    greeting = f"Hello, {first_name}" if first_name else "Hello, I'm Jin AI"

    # Dedicated animated HTML stage (bypasses Streamlit markdown sanitizer so animations always play)
    components.html(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
            body {{
                background: transparent;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                overflow: hidden;
                padding-top: 8px;
            }}
            .stage {{
                position: relative;
                width: 220px;
                height: 155px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-end;
            }}
            /* Swirling magical smoke trail from candle to Jin */
            .smoke {{
                position: absolute;
                bottom: 44px;
                width: 18px;
                height: 18px;
                border-radius: 50%;
                background: radial-gradient(circle, rgba(167,139,250,0.85) 0%, rgba(96,165,250,0) 70%);
                animation: smokeRise 1.6s ease-out infinite;
            }}
            .smoke.s2 {{ animation-delay: 0.45s; left: 95px; }}
            .smoke.s3 {{ animation-delay: 0.9s; left: 108px; }}

            @keyframes smokeRise {{
                0% {{ transform: translateY(0) scale(0.6); opacity: 0.95; }}
                50% {{ transform: translateX(-8px) translateY(-35px) scale(1.6); opacity: 0.6; }}
                100% {{ transform: translateX(8px) translateY(-75px) scale(2.4); opacity: 0; }}
            }}

            /* Jin emerging out of the candle flame */
            .jin {{
                font-size: 64px;
                line-height: 1;
                z-index: 3;
                margin-bottom: 10px;
                filter: drop-shadow(0 0 22px rgba(96, 165, 250, 0.85));
                animation: emergeFromCandle 1.25s cubic-bezier(0.22, 1, 0.36, 1) forwards,
                           hoverFloat 3s ease-in-out 1.25s infinite;
            }}
            @keyframes emergeFromCandle {{
                0% {{
                    opacity: 0;
                    transform: translateY(58px) scale(0.15) rotate(-12deg);
                    filter: blur(10px) brightness(2);
                }}
                65% {{
                    opacity: 1;
                    transform: translateY(-8px) scale(1.1) rotate(3deg);
                    filter: blur(0px) brightness(1.15);
                }}
                100% {{
                    opacity: 1;
                    transform: translateY(0px) scale(1) rotate(0deg);
                }}
            }}
            @keyframes hoverFloat {{
                0%, 100% {{ transform: translateY(0px); }}
                50% {{ transform: translateY(-8px); }}
            }}

            /* Flickering flame */
            .flame {{
                width: 14px;
                height: 22px;
                background: radial-gradient(circle at 50% 75%, #FFFBEB 10%, #FBBF24 45%, #F97316 85%, transparent 100%);
                border-radius: 50% 50% 50% 50% / 65% 65% 35% 35%;
                box-shadow: 0 0 18px #F59E0B, 0 0 32px #FBBF24;
                animation: flicker 0.9s ease-in-out infinite alternate;
                z-index: 2;
            }}
            @keyframes flicker {{
                0% {{ transform: scale(0.95) rotate(-3deg); }}
                100% {{ transform: scale(1.12) rotate(3deg); }}
            }}

            /* Glowing candle body & holder */
            .candle {{
                width: 24px;
                height: 30px;
                background: linear-gradient(180deg, #FEF3C7 0%, #F59E0B 100%);
                border-radius: 4px 4px 2px 2px;
                box-shadow: inset 0 -4px 8px rgba(180, 83, 9, 0.4);
            }}
            .holder {{
                width: 48px;
                height: 9px;
                background: linear-gradient(90deg, #B45309, #FBBF24, #B45309);
                border-radius: 10px;
                box-shadow: 0 4px 14px rgba(245, 158, 11, 0.45);
            }}

            .title {{
                margin-top: 14px;
                font-size: 32px;
                font-weight: 700;
                background: linear-gradient(90deg, #60A5FA, #A78BFA, #F472B6);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                text-align: center;
                animation: fadeUp 0.9s ease-out forwards;
            }}
            .subtitle {{
                margin-top: 6px;
                font-size: 14px;
                color: #9CA3AF;
                text-align: center;
                animation: fadeUp 1.1s ease-out forwards;
            }}
            @keyframes fadeUp {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
        </style>
        </head>
        <body>
            <div class="stage">
                <div class="jin">🧞</div>
                <div class="smoke"></div>
                <div class="smoke s2"></div>
                <div class="smoke s3"></div>
                <div class="flame"></div>
                <div class="candle"></div>
                <div class="holder"></div>
            </div>
            <div class="title">{greeting}</div>
            <div class="subtitle">Your wish is my command • Created by Shijin Shanavas</div>
        </body>
        </html>
        """,
        height=245,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧞 Who created Jin AI & what are his projects?", key="card_1"):
            st.session_state.pending_prompt = "Who created Jin AI? Tell me about Shijin Shanavas and his projects."
            st.rerun()
        if st.button("💻 Write clean Python code for binary search", key="card_2"):
            st.session_state.pending_prompt = (
                "Write clean, well-commented Python code for binary search and explain its time complexity."
            )
            st.rerun()
    with col2:
        if st.button("✨ Explain Artificial Intelligence simply", key="card_3"):
            st.session_state.pending_prompt = (
                "Explain Artificial Intelligence and Machine Learning in simple words with real-life examples."
            )
            st.rerun()
        if st.button("📈 How does Random Forest work in ML?", key="card_4"):
            st.session_state.pending_prompt = (
                "Explain how Random Forest works in Machine Learning with a simple real-world example."
            )
            st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if active_prompt:
    display_text = f"{active_prompt} *(Attached: {uploaded_doc.name})*" if uploaded_doc else active_prompt
    with st.chat_message("user"):
        st.markdown(display_text)

    with st.chat_message("assistant"):
        try:
            full_reply = st.write_stream(
                backend.stream_reply(
                    user_prompt=active_prompt,
                    chat_history=st.session_state.messages,
                    doc_bytes=uploaded_doc.getvalue() if uploaded_doc else None,
                    doc_mime=uploaded_doc.type if uploaded_doc else None,
                    ml_summary=st.session_state.ml_summary,
                    is_signed_in=_user_logged_in(),
                )
            )
            st.session_state.messages.append({"role": "user", "content": display_text})
            st.session_state.messages.append({"role": "assistant", "content": full_reply})
            backend.save_chat(user_id, st.session_state.active_chat_id, st.session_state.messages)
            st.rerun()
        except Exception as err:
            st.error(str(err))
