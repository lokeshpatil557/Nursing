import streamlit as st
from backend import get_relevant_docs, get_user_queries, store_user_query, translate_text, is_valid_email, query_gemini_agent
from langdetect import detect
import re

st.set_page_config(page_title="Fight Cancer", page_icon="🧬", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'email' not in st.session_state:
    st.session_state.email = ""
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'query_input' not in st.session_state:
    st.session_state.query_input = ""
if 'clear_input' not in st.session_state:
    st.session_state.clear_input = False

# Login Screen
if not st.session_state.logged_in:
    st.title("Login to Nurse Companion Agent")
    email = st.text_input("Enter your email ID:", "")
    if st.button("Login"):
        if email and is_valid_email(email):
            st.session_state.logged_in = True
            st.session_state.email = email
            st.rerun()
        else:
            st.warning("Please enter a valid email ID.")
else:
    st.title("🧬 Nurse Companion Agent")
    st.write(f"Logged in as: {st.session_state.email}")

    for role, text in st.session_state.chat_history:
        css_class = 'user-message' if role == "user" else 'bot-message'
        st.markdown(f"<div class='{css_class}'>{text}</div>", unsafe_allow_html=True)

    st.markdown("""
        <style>
            .user-message { background: #00796B; color: white; padding: 10px; border-radius: 10px; text-align: right; }
            .bot-message { background: #001F3F; color: white; padding: 10px; border-radius: 10px; }
        </style>
    """, unsafe_allow_html=True)

    if st.session_state.clear_input:
        st.session_state.query_input = ""
        st.session_state.clear_input = False
        st.rerun()

    with st.form(key="chat_form", clear_on_submit=False):
        query = st.text_input("Ask about nursing technique:", key="query_input")
        submitted = st.form_submit_button("Send")

    if submitted and query.strip():
        st.session_state.chat_history.append(("user", query))

        try:
            user_lang = detect(query)
        except:
            user_lang = "en"

        st.caption(f"Detected language: {user_lang}")
        
        supported_langs = ['en', 'es', 'zh-cn', 'zh-tw']
        if user_lang not in ['en', 'es', 'zh-cn', 'zh-tw']:
            st.warning("Currently, we only support English, Spanish, and Chinese.")
            msg = "❌ Sorry, we currently support only English, Spanish, and Chinese."
            st.session_state.chat_history.append(("bot", msg))
            st.session_state.clear_input = True
            st.rerun()

        translated_query = translate_text(query, target_lang='en') if user_lang != 'en' else query
        
        if re.search(r'\b(previous|past|history|asked about|my queries|queries|earlier)\b', translated_query, re.IGNORECASE):
            response_en = get_user_queries(st.session_state.email, translated_query)
            response = translate_text(response_en, target_lang=user_lang) if user_lang != 'en' else response_en
        else:
            relevant_docs, _ = get_relevant_docs(translated_query)
            context = "\n".join(relevant_docs)

            prompt = (
                f"You are a highly knowledgeable medical assistant with expertise in clinical decision making.\n\n"
                f"Based on the following medical content:\n\n{context}\n\n"
                f"Provide a structured response covering scientific insights, best practices, and guidelines.\n"
                f"Only respond if the information is at least 80% semantically relevant to the question.\n"
                f"Keep the response minimal and focused on the most important points.\n\n"
                f"Question: {translated_query}"
            )

            response_en = query_gemini_agent(prompt)
            response = translate_text(response_en,  target_lang=user_lang) if user_lang != 'en' else response_en

        store_user_query(st.session_state.email, query, response)
        st.session_state.chat_history.append(("bot", response))
        st.session_state.clear_input = True
        st.rerun()

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.email = ""
        st.session_state.chat_history = []
        st.rerun()
