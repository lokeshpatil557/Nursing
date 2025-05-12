import os
import re
import json
import sqlite3
from langdetect import detect
from langchain_community.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.agents import Tool, initialize_agent
from langchain.agents.agent_types import AgentType
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from translator_utils import translate_text

# Setup environment
os.environ["GOOGLE_API_KEY"] = "AIzaSyDwEUSuD2jTlWjN3d-DW5Pfj6vnzPiG4Tk"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
DB_PATH = "user_queries.sqlite"
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
nursing_vectorstore = Chroma(persist_directory="./pdf_docs_db", embedding_function=embedding_model)




    
# def translate_text(text, target='en'):
#     try:
#         translated = translator.translate(text, dest=target)
#         return translated.text
#     except Exception as e:
#         return f"Translation error: {e}"

def is_valid_email(email):
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(email_regex, email))



@tool
def search_nursing_pdf(query: str) -> str:
    """Searches nursing documents for relevant content."""
    results = nursing_vectorstore.similarity_search(query, k=3)
    return "\n".join([doc.page_content for doc in results])

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3)

tools = [
    Tool(
        name="Nursing PDF Retriever",
        func=search_nursing_pdf,
        description="Useful for answering questions from nursing manuals or documents."
    )
]

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent_type=AgentType.OPENAI_FUNCTIONS,
    verbose=False,
    handle_parsing_errors=True 
)

def query_gemini_agent(prompt: str):
    try:
        return agent.run(prompt)
    except Exception as e:
        return f"❌ Error: {str(e)}"

def get_relevant_docs(query, k=3):
    detected_lang = detect(query)
    translated_query = translate_text(query, target_lang='en') if detected_lang != 'en' else query
    results = nursing_vectorstore.similarity_search(translated_query, k=k)
    return [doc.page_content for doc in results], detected_lang

def store_user_query(email, query, response):
    if is_valid_email(email):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_queries (email, query, response)
            VALUES (?, ?, ?)
        """, (email, query, response))
        conn.commit()
        conn.close()
        return "✅ Query stored in database."
    return "⚠️ Invalid email format."

def get_user_queries(email, query, k=10):
    if not is_valid_email(email):
        return "⚠️ Invalid email format."

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT query, response FROM user_queries
        WHERE email = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (email, k))

    past_queries = cursor.fetchall()
    conn.close()

    if past_queries:
        reversed_queries = past_queries[::-1]
        formatted_queries = "\n".join([f"User: {q}\nResponse: {r}" for q, r in reversed_queries])
        prompt = (
            f"You are a highly knowledgeable medical assistant with expertise in nursing domain expertise.\n"
            f"Based on the following medical data:\n{formatted_queries}\n\n"
            f"Based on user and response think the user {query} and answer from provided {formatted_queries} match both user and response.\n"
            f"Question: {query}"
        )
        return query_gemini_agent(prompt)

    return "❌ No previous queries found for your email."
