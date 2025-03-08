import streamlit as st
import os
import random
import string
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings 
from langchain_community.vectorstores import FAISS
from langchain_core.tools import Tool 
from langchain_google_community import GoogleSearchAPIWrapper 
from langchain.agents import create_structured_chat_agent 
from langchain import hub 
from langchain.agents import AgentExecutor 
from pymongo import MongoClient 
from azure.core.credentials import AzureKeyCredential 
from azure.search.documents import SearchClient
from agentmemory import (
    get_memories
)
from streamlit_lottie import st_lottie
import requests
import time

def init():

    placeholder = st.empty()  # Create a placeholder for the loading screen
    progress_text = st.empty()  # Create a placeholder for updating messages

    with placeholder.container():
        col1, col2, col3 = st.columns([0.3, 2.7, 1.5])
        with col1:
            lottie_loading = load_lottilefile("https://lottie.host/c18a7e2c-0522-486d-8e37-b34f2fdabcf4/lkbEWMy7ej.json")
            st_lottie(
            lottie_loading,
            speed=1,
            reverse=False,
            loop=True,
            quality="medium",
            height = 110,
            width = 110,
            key=None
        )
            
        with col2:
            st.title("Initializing NTU Teaching Assistant Chatbot...")
        
        st.subheader("Please wait while the system sets up 👍.")
        progress_bar = st.progress(0)

        load_dotenv(override=True)

        #Setting up OpenAI LLM for Azure
        progress_text.write("Setting up Azure OpenAI...")
        st.session_state.openai_llm = AzureChatOpenAI(
            azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT'],
            api_key=os.environ['AZURE_OPENAI_APIKEY'],
            deployment_name=os.environ['AZURE_OPENAI_DEPLOYMENT_NAME'],
            model_name=os.environ['AZURE_OPENAI_MODEL_NAME'],
            api_version=os.environ['AZURE_OPENAI_API_VERSION'],
            temperature=0
        )
        progress_bar.progress(20)
        time.sleep(1)

        #Setting up FAISS vector store
        progress_text.write("Setting up FAISS vector store...")
        st.session_state.embeddings = AzureOpenAIEmbeddings(
                    azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT'], 
                    api_key=os.environ['AZURE_OPENAI_APIKEY'], 
                    model=os.environ['TEXT_EMBEDDING_MODEL_NAME'],
                    azure_deployment=os.environ['TEXT_EMBEDDING_DEPLOYMENT_NAME'])
        progress_bar.progress(30)
        time.sleep(1)


        #Setting up Google Search API functionality
        st.session_state.search_tool = Tool(
                name="google_search",
                description="Search Google for most recent and relevant results.",
                func=GoogleSearchAPIWrapper().run,
        )

        #Setting up Structured Chat Agent for google search API
        st.session_state.agent = create_structured_chat_agent(
                st.session_state.openai_llm, #LLM to use as the agent
                [st.session_state.search_tool], #Tools to use in the agent
                hub.pull("hwchase17/react")
        )

        # Assuming agent and tool are initialized correctly
        st.session_state.agent_executor = AgentExecutor(
                agent=st.session_state.agent,
                tools=[st.session_state.search_tool],
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=5,
        )

        #Setting up AI Azure Search
        progress_text.write("Setting up context indexes from Azure AI search...")
        st.session_state.courseinfo_search = SearchClient(
                endpoint=os.environ.get('AZURE_AI_SEARCH_ENDPOINT'), 
                index_name="information", 
                credential= AzureKeyCredential(os.environ.get('AZURE_AI_SEARCH_API_KEY'))
            )
        
        st.session_state.coursenotes_search = SearchClient(
                endpoint=os.environ.get('AZURE_AI_SEARCH_ENDPOINT'), 
                index_name="notes", 
                credential= AzureKeyCredential(os.environ.get('AZURE_AI_SEARCH_API_KEY'))
            )

        
        st.session_state.surveyquestions_search = SearchClient(
                endpoint=os.environ.get('AZURE_AI_SEARCH_ENDPOINT'), 
                index_name="survey_questions", 
                credential= AzureKeyCredential(os.environ.get('AZURE_AI_SEARCH_API_KEY'))
            )
        
        progress_bar.progress(50)
        time.sleep(1)

        # Connect to the chatbot database to update survey data
        progress_text.write("Connecting to chatbot database...")
        st.session_state.sql_client = MongoClient(os.environ['PYMONGO_CONNECTION_STRING'])
        progress_bar.progress(70)
        time.sleep(1)

        progress_text.write("Loading session states and chat history...")
        if 'conversation' not in st.session_state:
            st.session_state.conversation = []
        if 'messages' not in st.session_state:
            st.session_state.messages = []                                        
        if 'survey_shown' not in st.session_state:
            st.session_state.survey_shown = False
        if 'survey_questions' not in st.session_state:
            st.session_state.survey_questions = []
        if 'survey_responses' not in st.session_state:
            st.session_state.survey_responses = []
        if 'conversation_id' not in st.session_state:
            st.session_state.conversation_id = generate_random_code(8)
        if 'new_conversation' not in st.session_state:
            st.session_state.new_conversation = True
        if 'new_conversation_title' not in st.session_state:
            st.session_state.conversation_title = None
        if 'cached_human_memories' not in st.session_state:
            st.session_state.cached_human_memories = get_memories(category='human', sort_order="desc")
        if 'cached_ai_memories' not in st.session_state:
            st.session_state.cached_ai_memories = get_memories(category='ai', sort_order="desc")
        if 'username' not in st.session_state:
            st.session_state.username = None
        if 'chatbot_context' not in st.session_state:
            st.session_state.chatbot_context = None
            chatbot_db = st.session_state.sql_client['chatbot']  # Use the chatbot database
            context_collection = chatbot_db['chatbot_context']
            st.session_state.chatbot_context = (existing_context := context_collection.find_one({}, {"_id": 0, "context": 1})) and existing_context.get("context", "")

        progress_bar.progress(90)
        time.sleep(1)

    # Clear the placeholder once setup is complete
    placeholder.empty()
    # Hide the progress bar and text
    progress_text.empty()

#To generate random ID for each new conversation
def generate_random_code(length=8):
    characters = string.ascii_letters + string.digits  # Letters (both uppercase and lowercase) + digits
    random_code = ''.join(random.choice(characters) for _ in range(length))
    return random_code

def load_lottilefile(url):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()
