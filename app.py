import pandas as pd
import streamlit as st
import backend

st.set_page_config(
    page_title="Jin AI",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .block-container {
        padding-top: 2.2rem;
        padding-bottom: 5rem;
        max-width: 800px;
    }

    .hero-title {
        font-size: 2.6rem;
        font-weight: 700;
        background: linear-gradient(90deg, #60A5FA, #A78BFA, #F472B6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-top: 2rem;
        margin-bottom: 0.3rem;
    }
    .hero-subtitle {
        text-align: center;
        color: #9CA3AF;
        font-size: 1.02rem;
        margin-bottom: 2rem;
    }

    div.stButton > button {
        width: 100%;
        border-radius: 12px;
        border: 1px solid #2D333B;
        background-color: #161B22;
        color: #E6EDF3;
        padding: 0.72rem 0.95rem;
        text-align: left;
        font-size: 0.9rem;
        transition: all 0.18s ease;
    }
    div.stButton > button:hover {
        border-color: #60A5FA;
        background-color: #1F2937;
    }

    [data-testid="stChatMessage"] {
        border-radius: 16px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.6rem;
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

with st.sidebar:
    st.markdown("### ✨ Jin AI")

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
                st.warning("Configure `[auth]` in `.streamlit/secrets.toml` to enable Google Sign-In.")
        st.caption("Sign in to sync chat history across sessions.")

user_input = st.chat_input("Message Jin AI...")
active_prompt = st.session_state.pending_prompt or user_input
st.session_state.pending_prompt = None

if not st.session_state.messages and not active_prompt:
    first_name = st.user.get("given_name", "") if _user_logged_in() else ""
    greeting = f"Hello, {first_name}" if first_name else "Hello, I'm Jin AI"
    st.markdown(f'<div class="hero-title">{greeting}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">Created by Shijin Shanavas • AI Assistant & ML Copilot</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("👤 Who created Jin AI & what are his projects?", key="card_1"):
            st.session_state.pending_prompt = "Who created Jin AI? Tell me about Shijin Shanavas and his projects."
            st.rerun()
        if st.button("💻 Write clean Python code for binary search", key="card_2"):
            st.session_state.pending_prompt = (
                "Write clean, well-commented Python code for binary search and explain its time complexity."
            )
            st.rerun()
    with col2:
        if st.button("🌏 Explain Artificial Intelligence in simple words", key="card_3"):
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