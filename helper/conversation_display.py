import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
import re
from helper.response import *
import datetime
from agentmemory import (
    create_memory
)
from helper.survey import *
from helper.survey_gen import *
import string
import random

def generate_chat_timestamp():
    """
    Generates the current date and time for a chat message.

    Returns:
        str: The current date and time formatted as 'YYYY-MM-DD HH:MM:SS'.
    """
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    return timestamp

def generate_random_code(length=8):
    characters = string.ascii_letters + string.digits  # Letters (both uppercase and lowercase) + digits
    random_code = ''.join(random.choice(characters) for _ in range(length))
    return random_code

def append_chat(role, msg):

    current_datetime = generate_chat_timestamp()

    metadata = {
        'username': st.session_state.get('username', 'Anonymous'),
        'conversation': st.session_state.conversation_id,
        'conversation_title': st.session_state.conversation_title,
        'datetime': current_datetime
    }

    # Update cache FIRST
    new_memory = {
        'role': role,
        'document': msg,
        'metadata': metadata
    }

    if role == 'human':

        #Add human message to the cached human memories
        st.session_state.cached_human_memories.insert(0, new_memory)

        #Add human message to the conversation history
        st.session_state.conversation.append(HumanMessage(content=msg))

        #Permanent storage of the human message in the database
        create_memory("human", msg, metadata=metadata)
        
    elif role == "ai":

        #Add AI message to the cached AI memories
        st.session_state.cached_ai_memories.insert(0, new_memory)
        
        # Add AI message to the conversation history
        st.session_state.conversation.append(AIMessage(content=msg))

        #Permanent storage of the human message in the database
        create_memory("ai", msg, metadata=metadata)
    
    st.session_state.messages.append({"role": role, "content": msg})

def main_chatbot_interface():
    # Display chat history
    display_chat_history()

    # Check if the survey is active
    if st.session_state.get('survey_shown', False):
        show_survey()
    else:
        st.title("NTU Chatbot Helper")
        st.markdown(f"Ask me anything about **_{st.session_state.chatbot_context}_**.")

        # Display existing messages
        for msg in st.session_state.messages:
            if msg['role'] == 'human':
                with st.chat_message("user"):
                    st.markdown(msg['content'])
            elif msg['role'] == 'ai':
                with st.chat_message("ai"):
                    st.markdown(msg['content'])
                    if "https://www.youtube.com/watch?v=" in msg['content']:
                        youtube_link = re.search(r'https://www\.youtube\.com/watch\?v=[\w-]+', msg['content'])
                        if youtube_link:
                            VIDEO_DATA = youtube_link.group(0)
                            _, container, _ = st.columns([1, 7, 14])
                            container.video(VIDEO_DATA)

        # Then check survey status after processing input
        survey_pending = ('survey_questions' in st.session_state 
                          and len(st.session_state.survey_questions) > 0
                          and len(st.session_state.survey_responses) < len(st.session_state.survey_questions))

        if survey_pending:
            # Show survey prompt button
            st.info("Please complete the survey to continue chatting.")
            if st.button("📝 Take survey"):
                st.session_state.survey_shown = True
                st.rerun()
            st.chat_input("Enter your question here", disabled=True)
            

        else:
            # Process user input first
            if user_input := st.chat_input("Enter your question here"):
                # Append user message
                with st.chat_message("user"):
                    st.markdown(user_input)
                append_chat("human", user_input)
                
                # Generate AI response
                with st.chat_message('ai'):
                    ai_response = answer(user_input)
                    st.markdown(ai_response)
                append_chat("ai", ai_response)

                # Check if survey was triggered and force rerun
                if 'survey_questions' in st.session_state and len(st.session_state.survey_questions) > 0:
                    st.rerun()

        
def display_chat_history():

    # Get today's date and calculate the date ranges for previous 7 and 30 days
    today = datetime.date.today()
    one_day_ago = today - datetime.timedelta(days=1)
    seven_days_ago = today - datetime.timedelta(days=7)
    thirty_days_ago = today - datetime.timedelta(days=30)

    with st.sidebar:
        st.markdown(f"# {st.session_state.username}'s Chat History")

        # New Conversation Button
        if st.button("New Conversation", key="new_conversation_button"):
            # Clear previous conversations and messages in session state
            st.session_state.conversation = []  # Reset the conversation list
            st.session_state.messages = []  # Reset the messages list
            st.session_state.conversation_id = generate_random_code(8)  # Generate a new conversation ID
            st.session_state.new_conversation = True
            st.session_state.conversation_title = None

        # Retrieve combined chat histories
        conversations = get_conversation_ids()

        # Convert datetime string to date object for comparison
        def get_date_from_datetime(datetime_str):
            return datetime.datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S').date()

        # Today's conversations
        st.markdown("#### Today")
        today_conversations = [conv for conv in conversations if get_date_from_datetime(conv['datetime']) == today]
        for i, conv in enumerate(today_conversations):
            if st.button(f"Chat {i + 1}: {conv['conversation_id']} {conv['conversation_title']}", key=f"today_{conv['conversation_id']}"):
                 get_combined_memories(conv['conversation_id'])
                 st.session_state.conversation_id = conv['conversation_id']
                 st.session_state.conversation_title = conv['conversation_title']
                 st.session_state.new_conversation = False

        # Yesterday's conversations
        st.markdown("#### Yesterday")
        yesterday_conversations = [conv for conv in conversations if get_date_from_datetime(conv['datetime']) == one_day_ago]
        for i, conv in enumerate(yesterday_conversations):
            if st.button(f"Chat {i + 1}: {conv['conversation_id']} {conv['conversation_title']}", key=f"yesterday_{conv['conversation_id']}"):
                 get_combined_memories(conv['conversation_id'])
                 st.session_state.conversation_id = conv['conversation_id']
                 st.session_state.conversation_title = conv['conversation_title']
                 st.session_state.new_conversation = False

        # Previous 7 Days' conversations
        st.markdown("#### Previous 7 Days")
        last_seven_days_conversations = [conv for conv in conversations if seven_days_ago <= get_date_from_datetime(conv['datetime']) < one_day_ago]
        for i, conv in enumerate(last_seven_days_conversations):
            if st.button(f"Chat {i + 1}: {conv['conversation_id']} {conv['conversation_title']}", key=f"last7days_{conv['conversation_id']}"):
                 get_combined_memories(conv['conversation_id'])
                 st.session_state.conversation_id = conv['conversation_id']
                 st.session_state.conversation_title = conv['conversation_title']
                 st.session_state.new_conversation = False

        # Previous 30 Days' conversations
        st.markdown("#### Previous 30 Days")
        last_thirty_days_conversations = [conv for conv in conversations if thirty_days_ago <= get_date_from_datetime(conv['datetime']) < seven_days_ago]
        for i, conv in enumerate(last_thirty_days_conversations):
            if st.button(f"Chat {i + 1}: {conv['conversation_id']} {conv['conversation_title']}", key=f"last30days_{conv['conversation_id']}"):
                 get_combined_memories(conv['conversation_id'])
                 st.session_state.conversation_id = conv['conversation_id']
                 st.session_state.conversation_title = conv['conversation_title']
                 st.session_state.new_conversation = False

#@st.cache_data #Not sure whether this works yet
def get_conversation_ids():
    ai_memories = st.session_state.cached_ai_memories
    # Dictionary to store the earliest timestamp for each conversation ID
    conversations = {}
    
    for ai in ai_memories:
        # Check if the username matches (if provided)
        username = ai.get('metadata', {}).get('username')
        if username != st.session_state.username:
            continue  # Skip other users' conversations
        conversation_id = ai.get('metadata', {}).get('conversation')
        datetime_str = ai.get('metadata', {}).get('datetime')
        conversation_title = ai.get('metadata', {}).get('conversation_title')
        
        if conversation_id:
            # Parse the datetime string
            current_datetime = datetime.datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
            
            if conversation_id not in conversations:
                # If this is the first time we're seeing this conversation ID,
                # initialize it with the current timestamp
                conversations[conversation_id] = {
                    'conversation_id': conversation_id,
                    'datetime': datetime_str,
                    'conversation_title': conversation_title,
                    'username': st.session_state.username
                }
            else:
                # If we've seen this conversation before, keep the earlier timestamp
                existing_datetime = datetime.datetime.strptime(
                    conversations[conversation_id]['datetime'],
                    '%Y-%m-%d %H:%M:%S'
                )
                if current_datetime < existing_datetime:
                    conversations[conversation_id]['datetime'] = datetime_str

                # Update title if current entry has no title but new memory has one
                if not conversations[conversation_id].get('title') and conversation_title:
                    conversations[conversation_id]['title'] = conversation_title
    
    # Convert the dictionary values to a list
    return list(conversations.values())

def get_combined_memories(conversation_id):
    # Clear previous conversations and messages in session state
    st.session_state.conversation = []
    st.session_state.messages = []

    # Filter and sort messages by timestamp in ascending order (oldest first)
    human_memories = sorted(
        [human for human in st.session_state.cached_human_memories 
         if human.get('metadata', {}).get('conversation') == conversation_id
         and human.get('metadata', {}).get('username') == st.session_state.username],
        key=lambda x: x['metadata']['datetime']
    )
    
    ai_memories = sorted(
        [ai for ai in st.session_state.cached_ai_memories 
         if ai.get('metadata', {}).get('conversation') == conversation_id
         and ai.get('metadata', {}).get('username') == st.session_state.username],
        key=lambda x: x['metadata']['datetime']
    )

    # Pair messages and add to session state
    for human, ai in zip(human_memories, ai_memories):
        st.session_state.conversation.append(HumanMessage(content=human['document']))
        st.session_state.messages.append({"role": "human", "content": human['document']})
        
        st.session_state.conversation.append(AIMessage(content=ai['document']))
        st.session_state.messages.append({"role": "ai", "content": ai['document']})


