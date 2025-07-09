import streamlit as st
from langchain_core.messages import HumanMessage
from survey_gen import *

def generate_conversation_title(query):
    title_prompt = f"""
    Generate a short, relevant, and engaging title for a conversation based on the user's query: "{query}". 
    The title should reflect the topic or theme of the question in a concise manner, 
    capturing the essence of the conversation while being easily understandable. 
    The title should be formatted as a sentence or phrase, ideally between 3 to 6 words.
    """
    title_response = st.session_state.openai_llm.invoke(title_prompt).content

    st.session_state.new_conversation = False

    return title_response

def is_relevant_to_information(query):

    vector_query_content = VectorizableTextQuery(text=query, k_nearest_neighbors=50, fields="content_vector")
    context = st.session_state.information_search.search(search_text=query, vector_queries=[vector_query_content], top=3)

    contexts = ""
    for con in context:
        contexts += con['content'] + "\n" 
    
    print(contexts)

    information_relevance_prompt = f"""
    You are given the context and the query. The context contains tailored information from a Azure AI Search index.
    Your task is to use the context retrieved to properly answer the query as well as you can. 
    If the context does not contains sufficient information, then you are not able to properly answer the query.

    Query: "{query}" 
    Context: {contexts}

    Respond in JSON format with two fields:
    1. "relevant": Boolean value (true/false) indicating whether you can answer the query using the context.
    2. "response": If relevant is true, provide a well-formatted, helpful response based on the context.
                   If relevant is false, set this to "I'm sorry, I don't have enough context to answer that question."

    Example response for sufficient context:
    {{
        "relevant": true,
        "response": [WELL-FORMATTED RESPONSE]
    }}
    
    Example response for insufficient context:
    {{
        "relevant": false,
        "response": "I'm sorry, I don't have enough context to answer that question."
    }}

    Important: Ensure your response is valid JSON that can be parsed programmatically.
    """

    response = st.session_state.openai_llm.invoke(information_relevance_prompt).content

    try:
        # Check if response contains ```json before processing
        if response.startswith("```json") and response.endswith("```"):
            clean_json = response.replace('```json', '').replace('```', '').strip()
        else:
            clean_json = response  # No need to clean if not wrapped in ```json
        
        result = json.loads(clean_json)  # Attempt to parse JSON
        return result

    except json.JSONDecodeError as e:
        # Print/log the actual error for debugging
        print(f"JSON Decode Error: {e}")  
        return {
            "relevant": False,
            "response": "An error occurred while processing your request. Please try again later."
        }

def is_relevant_to_notes(query):

    # Search for relevant context in the vector store
    vector_query_content = VectorizableTextQuery(text=query, k_nearest_neighbors=50, fields="content_vector")
    context = st.session_state.notes_search.search(search_text=query, vector_queries=[vector_query_content], top=3)
    contexts = ""
    for con in context:
        contexts += con['content'] + "\n" 
        
    notes_relevance_prompt = f"""
    You are given the context and the query. The context contains tailored notes from an Azure AI Search index.
    Your task is to use the context retrieved to properly answer the query as well as you can. 
    If the context does not contains sufficient information, then you are not able to properly answer the query.

    Query: "{query}"
    Context: {contexts}

    Respond in JSON format with two fields:
    1. "relevant": Boolean value (true/false) indicating whether you can answer the query using the context.
    2. "response": If relevant is true, provide a well-formatted, helpful response based on the context.
                   If relevant is false, set this to "I'm sorry, I don't have enough context to answer that question."

    Example response for sufficient context:
    {{
        "relevant": true,
        "response": [WELL-FORMATTED RESPONSE]
    }}
    
    Example response for insufficient context:
    {{
        "relevant": false,
        "response": "I'm sorry, I don't have enough context to answer that question."
    }}

    Important: Ensure your response is valid JSON that can be parsed programmatically.
    """

    response = st.session_state.openai_llm.invoke(notes_relevance_prompt).content
    
    try:
        # Check if response contains ```json before processing
        if response.startswith("```json") and response.endswith("```"):
            clean_json = response.replace('```json', '').replace('```', '').strip()
        else:
            clean_json = response  # No need to clean if not wrapped in ```json
        
        result = json.loads(clean_json)  # Attempt to parse JSON
        return result

    except json.JSONDecodeError as e:
        # Print/log the actual error for debugging
        print(f"JSON Decode Error: {e}")  
        return {
            "relevant": False,
            "response": "An error occurred while processing your request. Please try again later."
        }
    
def is_relevant_to_context(query):

    domain = st.session_state.chatbot_context

    # Step 1: Initial Relevance Check
    primary_prompt = f"""
    Determine if this query is relevant to {domain}.

    Query: "{query}"

    Consider relevant if it relates to:
    1. Core concepts or practices in {domain}
    2. Common tools/technologies used in {domain}
    3. Standard procedures in {domain}
    4. Typical user needs in {domain}

    Respond ONLY with 'Yes' or 'No'.
    """
    primary_response = st.session_state.openai_llm.invoke(primary_prompt).content.lower()

    if "yes" in primary_response:
        return True

    fallback_prompt = f"""
    You marked the query "{query}" as irrelevant to "{domain}" in an earlier query.
    Please do a more thorough secondary check to determine if the query is relevant to {domain}.

    Evaluation Steps:
    1. Identify any implicit references to {domain} concepts
    2. Check for domain-specific terminology patterns
    3. Consider common paraphrasing of {domain} topics
    4. Assess if non-domain items could relate to {domain} workflows

    Respond ONLY with 'Yes' or 'No'.
    """
    fallback_response = st.session_state.openai_llm.invoke(fallback_prompt).content

    # Step 2: If "Yes," return True
    if "yes" in fallback_response:
        return True

    # Step 5: Final Decision
    return False

def generate_relevant_answer_with_links(query, notes_response):

    # Primary Answer Generation Prompt
    answer_prompt = f"""
    You are an experienced educator explaining concepts to students at various learning levels. 

    Address this query: "{query}"

    Provided explanation from notes: {notes_response}

    **Response Requirements:**
    1. Provide two distinct explanations:
    - First, create your OWN clear, concise explanation using simple language
    - Then integrate key points from provided notes (if available) as supplemental information

    2. Structure your response as:
    ### Conceptual Explanation:
    - 1-2 paragraph plain-language overview
    - Include real-world examples/analogies where applicable
    - Highlight common misunderstandings
    - Use bullet points for key takeaways

    ### Supplemental Explanation From Notes:
    - [Only if notes exist] Summarize key points from reference materials
    - Never repeat your original explanation verbatim

    ### Verified Resources:
    - Suggest 3 authoritative sources meeting these criteria:
        * Government/educational domains (.gov/.edu) or established platforms (Khan Academy, Britannica)
        * Directly relevant to query subtopics
        * Active links (test URL formatting)
    - Include 1 YouTube video from official educational channels (CrashCourse, TED-Ed, MIT OpenCourseWare) or videos with >100k views & >90% likes

    **Format Example:**
    ### Conceptual Explanation: 
    [Your original explanation here...]

    ### Supplemental Explanation From Notes: 
    - [Condensed note point 1]
    - [Condensed note point 2] 

    ### Verified Resources:
    1. [Resource Title] - [Full URL]
    - Domain type/credentials (e.g., "NIH medical resource")
    2. [Interactive Simulation: Topic] - [URL]
    3. [Research Paper Summary] - [URL]

    ### Recommended Video:
    - [Video Title] by [Creator] - [URL]
    - Duration & content focus (e.g., "12-min visual guide to X process")

    **Quality Checks:**
    - If query requires technical terms, provide simple definitions in parentheses
    - Flag any debated/controversial aspects of the topic
    - Prioritize ADA-compliant resources for accessibility
    - Never include paywalled resources
    """

    # Invoke the OpenAI LLM
    ai_response = st.session_state.openai_llm.invoke(answer_prompt).content
    return ai_response

# Function to invoke the LLM to determine if the current query is related to past messages in the same conversation
def if_related_to_past_conversations(query):

    # Get the past 3 conversations between the human and AI
    past_messages = st.session_state.conversation[-8:-1].copy() if len(st.session_state.conversation) > 1 else []
    
    # If there are no previous messages, it can't be related
    if not past_messages:
        return {"is_related": False, "relevant_context": ""}
    
    # Create the context for the LLM
    context_query = f"""
    Analyze if the current query continues or relates to the previous conversations.

    ### Previous Conversations [ordered chronologically from the earliest (top) to the latest (bottom)]:
    {past_messages}

    ### Current Query: "{query}"
    
    ### Analysis Criteria:
    1. LINGUISTIC CONTINUITY
       - Contains follow-up phrases: "tell me more", "explain further", "elaborate", etc.
       - Uses pronouns referring to previous content (it, that, this, those, etc.)
       - Contains elliptical expressions (incomplete sentences that rely on previous context)
    
    2. SEMANTIC CONTINUITY
       - References specific terms, concepts, or entities mentioned in previous messages
       - Asks questions about previously discussed topics
       - Requests examples or details about a previously introduced subject
       - Builds upon or challenges information provided earlier
    
    3. FUNCTIONAL CONTINUITY
       - Answers a question posed in the previous messages
       - Provides requested information from previous turns
       - Refers to a requested action mentioned earlier

    Return a JSON object with the following structure:
    {{
        "is_related": true/false,
        "relevant_query": "If related, include the specific query or queries that are relevant to the current query. If not related, leave this empty.",
        "relevant_response": "If related, include the specific parts of previous conversations that are relevant to the current query. Extract only the most essential information needed to understand the context of the current query. If not related, leave this empty."
    }}
    
    Important: Ensure your response is valid JSON that can be parsed programmatically.
    """

    # Invoke the LLM to check for relevance
    response = st.session_state.openai_llm.invoke([HumanMessage(content=context_query)]).content
    print("past convo", response)

    try:
        # Check if response contains ```json before processing
        if response.startswith("```json") and response.endswith("```"):
            clean_json = response.replace('```json', '').replace('```', '').strip()
        else:
            clean_json = response  # No need to clean if not wrapped in ```json
        
        result = json.loads(clean_json)  # Attempt to parse JSON
        return result

    except json.JSONDecodeError as e:
        # Print/log the actual error for debugging
        print(f"JSON Decode Error: {e}")  
        return {
            "relevant": False,
            "response": "An error occurred while processing your request. Please try again later."
        }
    
def continue_from_previous_conversation(query, conversation_history, info_reponse):
    context_query = f"""
    In our previous conversation, we discussed {conversation_history}.

    The current query is: "{query}"

    Additional information (if needed): {info_reponse}

    Your task is to continue the conversation from the previous context using the additional information if required.

    Return a response that seamlessly connects the previous conversation with the current query. Feel free to elaborate as much as needed.
    """

    response = st.session_state.openai_llm.invoke([HumanMessage(content=context_query)]).content

    return response

def answer(query):
    
    with st.spinner("Thinking..."):
        if st.session_state.new_conversation:
            st.session_state.conversation_title = generate_conversation_title(query)
        st.session_state.survey_questions = find_exact_matches_intersection(query)

    # Firstly, we check whether current query is related to previous conversations
    with st.spinner("Checking past conversations..."):
        is_relevant_to_past = if_related_to_past_conversations(query)
        print(is_relevant_to_past)

    if is_relevant_to_past["is_related"]:
        conversation_query = is_relevant_to_past["relevant_query"]
        conversation_history = is_relevant_to_past["relevant_response"]
        
        # Use the previous query/queries to search for useful information from information index
        with st.spinner("Searching for relevant information..."):
            info_response = is_relevant_to_information(conversation_query)
        
        # If information found, continue from previous conversation
        if info_response["relevant"]:
            info_response = info_response["response"]
            return continue_from_previous_conversation(query, conversation_history, info_response)
        
        # Check notes if no information found
        with st.spinner("Checking notes for relevant context..."):
            relevant_to_notes = is_relevant_to_notes(conversation_query)
        
        if relevant_to_notes["relevant"]:
            with st.spinner("Formulating answer..."):
                notes_response = relevant_to_notes["response"]
                return continue_from_previous_conversation(query, conversation_history, notes_response)
        else:
            if is_relevant_to_context(conversation_query):
                with st.spinner("Formulating answer..."):
                    return continue_from_previous_conversation(query, conversation_history, notes_response = "None")
            else:
                return f"My area of expertise is in {st.session_state.chatbot_context}. Ask related questions."

    else:

        with st.spinner("Searching for relevant information..."):
            info_response = is_relevant_to_information(query)
            print(info_response)
        
        if info_response["relevant"]:
            return info_response["response"]
        
        with st.spinner("Checking notes for relevant context..."):
            relevant_to_notes = is_relevant_to_notes(query)
            print(relevant_to_notes)
        
        if relevant_to_notes["relevant"]:
            with st.spinner("Formulating answer..."):
                notes_response = relevant_to_notes["response"]
                return generate_relevant_answer_with_links(query, notes_response)
        else:
            if is_relevant_to_context(query):
                with st.spinner("Formulating answer..."):
                    return generate_relevant_answer_with_links(query, notes_response="None")
            else:
                return f"My area of expertise is in {st.session_state.chatbot_context}. Ask related questions."


