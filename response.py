import streamlit as st
from langchain_core.messages import HumanMessage
from agentmemory import get_memories
import time
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
    print("Primary relevance check:", primary_response)

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
    print("Secondary relevance check:", fallback_response)

    # Step 2: If "Yes," return True
    if "yes" in fallback_response:
        return True

    # Step 5: Final Decision
    return False

def is_relevant_to_course(query):
    """
    Determine whether the query is about the course's administrative or logistical aspects.
    Examples of relevant queries:
    - "Who are the course coordinators?"
    - "What are the exam topics?"
    - "How do I access the course materials?"
    """
    relevance_prompt = f"""
    Determine if the following query is about administrative or logistical aspects of the course,
    such as coordinators, exam topics, schedules, or access to materials.

    Query: "{query}"

    Answer with a simple 'Yes' or 'No'.
    """
    relevance_check = st.session_state.openai_llm.invoke(relevance_prompt).content.lower().strip()
    print("Course relevance:", relevance_check)

    return relevance_check == "yes"


def find_answer_from_notes(query):
    """
    Generate a concise answer to a query related to Data Science and AI with a maximum of 3 sentences,
    followed by relevant links to source materials.
    """

    # Search for relevant context in the vector store
    vector_query_content = VectorizableTextQuery(text=query, k_nearest_neighbors=50, fields="content_vector")
    context = st.session_state.coursenotes_search.search(search_text=query, vector_queries=[vector_query_content], top=3)
    contexts = ""
    for con in context:
        contexts += con['content'] + "\n\n" 
        
    #print("Notes Contexts:", contexts)
            
    context_query = f"""
        Please go through the context and see if you can answer the user's query.\n
        Context: {contexts}
        Query: {query}

        If you you canfind an answer in the context, reply with "yes"
        If you cannot find an answer in the context, please reply with "no"
    """
    
    ai_notes_response = st.session_state.openai_llm.invoke(context_query).content.lower().strip()
    print("Can find from notes?:", ai_notes_response)

    return ai_notes_response == "yes"


def generate_relevant_answer_with_links(query):

    # Search for relevant context in the vector store
    vector_query_content = VectorizableTextQuery(text=query, k_nearest_neighbors=50, fields="content_vector")
    context = st.session_state.coursenotes_search.search(search_text=query, vector_queries=[vector_query_content], top=3)
    contexts = ""
    for con in context:
        contexts += con['content'] + "\n\n" 
            
    context_query = f"""
        Analyze the provided context and answer the query using ONLY information from the context.\n
        Context: {contexts}
        Query: {query}

        If you cannot find an answer in the context, please reply with 'Explanation from notes: No information of this question in the notes.'
    """

    ai_notes_response = st.session_state.openai_llm.invoke(context_query).content

    #print("Generated AI Notes Answer:", ai_notes_response)

    # Primary Answer Generation Prompt
    answer_prompt = f"""
    You are an experienced educator explaining concepts to students at various learning levels. 

    Address this query: "{query}"

    Provided explanation from notes: "{ai_notes_response}"

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

    print("Generated AI Answer:", ai_response)

    return ai_response

# Function to invoke the LLM to determine if the current query is related to past messages in the same conversation
def check_if_related_to_past_conversations(current_query):
    # Get the past 3 conversations between the human and AI
    past_messages = st.session_state.conversation[-10:-1].copy() if len(st.session_state.conversation) > 1 else []
    print(past_messages)
    # If there are no previous messages, it can't be related
    if not past_messages:
        return False
    
    # Create the context for the LLM
    context_query = f"""
    Analyze if the current query continues or relates to the previous conversations.

    ### Previous Conversations:
    {past_messages}

    ### Current Query: {current_query}
    
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

    If ANY of these criteria are met, the query is related to the previous conversation.
    
    Answer with ONLY Yes' or 'No'.
    """

    # Invoke the LLM to check for relevance
    response = st.session_state.openai_llm.invoke([HumanMessage(content=context_query)]).content
    print("Relevant to previous queries or not", response)
    return response.strip().lower() == 'yes'

def answer(query):
    # Initialize a variable to hold the final answer
    final_answer = ""

    if st.session_state.new_conversation:
        # Generate a title for the new conversation
        st.session_state.conversation_title = generate_conversation_title(query)

    with st.spinner('Checking whether related to course...'):
        relevant_to_course = is_relevant_to_course(query)
        time.sleep(0.5)

    if relevant_to_course:
        # Search for relevant context in the vector store
        vector_query_content = VectorizableTextQuery(text=query, k_nearest_neighbors=50, fields="content_vector")
        context = st.session_state.courseinfo_search.search(search_text=query, vector_queries=[vector_query_content], top=3)
        contexts = ""
        for con in context:
            contexts += con['content'] + "\n\n" 
        
        print(contexts)
            
        context_query = f"""
            Please format and answer the user query based on the following provided below.\n
            Context: {contexts}
            Query: {query}

            If you cannot find the answer in the context, please reply with 'Please email the professor for further assistance' and do not try to make up an answer.
        """
        
        # Try to get an answer from the primary OpenAI LLM
        with st.spinner('Formulating an answer based on the provided context...'):
            final_answer = st.session_state.openai_llm.invoke([HumanMessage(content=context_query)]).content
            #time.sleep(0.5)
        st.session_state.survey_questions = find_exact_matches_intersection(query)

    else:
        # Check relevance to data science and AI
        with st.spinner('Checking if query is related to context...'):
            is_relevant = is_relevant_to_context(query)
            time.sleep(0.5)

        # Check if the query is related to past conversations
        with st.spinner('Checking if the query continues a past conversation...'):
            is_continuation = check_if_related_to_past_conversations(query)
            time.sleep(0.5)
        
        with st.spinner('Checking whether question is related to notes...'):
            is_notes = find_answer_from_notes(query)

        # Preliminary check if the query is relevant
        if not ((is_relevant or is_continuation) or is_notes):
            final_answer = "My area of expertise is the context specified only. Please ask a question related to this topic."
        else:
            if is_continuation:
                # Pull the conversation history
                with st.spinner('Retrieving past conversation history...'):
                    current_conversation_context = st.session_state.conversation[-10:].copy()

                # Now create the context for the LLM, combining memory and history
                context_query = f"""
                    Retrieved past conversation messages: {current_conversation_context}
                    Current query: {query}

                    The latest human and AI messages are at the bottom of the retrieved past conversation messages. 
                    Read all of the past messages and figure out which messages will be the most suitable to use as reference to the current query.
                    Then, answer the current query as best as you can.
                """
                
                # Invoke the OpenAI LLM for further answer
                with st.spinner('Formulating answer based on past conversation memories...'):
                    final_answer = st.session_state.openai_llm.invoke([HumanMessage(content=context_query)]).content
                    #time.sleep(0.5)
                st.session_state.survey_questions = find_exact_matches_intersection(query)

            else:
                # Get an answer from the primary OpenAI LLM
                with st.spinner('Formulating the best answer possible...'):
                    final_answer = generate_relevant_answer_with_links(query)
                    #time.sleep(0.5)
                st.session_state.survey_questions = find_exact_matches_intersection(query)

    return final_answer  # Return the final answer at once
