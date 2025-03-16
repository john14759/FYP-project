from azure.search.documents.models import VectorizableTextQuery
import json
import streamlit as st
import re

def hybrid_search(query, top_k=5):

    # Generate query embedding using your embedding model
    vector_query_content = VectorizableTextQuery(text=query, k_nearest_neighbors=50, fields="content_vector", weight =1.5)

    vector_query_tags = VectorizableTextQuery(text=query, k_nearest_neighbors=50, fields="tags_vector", weight =0.5)
   
    # Perform the hybrid search
    try:
        results = st.session_state.surveyquestions_search.search(
            search_text=query,  # Use None for pure vector search
            vector_queries=[vector_query_content, vector_query_tags],
            select=["id", "content", "tags"],
            top=top_k
        )

        content= [result['content'] for result in results]

        return content
    except Exception as e:
        print(f"Error performing vector search: {e}")
        return []

# This returns all the indices in the current index
def search_all():

    all_docs = []
    try:
        results = st.session_state.surveyquestions_search.search(
            search_text = "*",
            select = ["content"],
            top = 1000,
        )
        for doc in results:
            all_docs.append(doc["content"])
        
        return all_docs
    
    except Exception as e:
        print(f"Error performing vector search: {e}")
        return []

def query_search(query):
    all_questions = search_all()
    
    relevance_prompt = f"""
        Analyze the following user query: "{query}"
        
        Below is a list of available survey questions:
        {all_questions}
        
        Select 3-5 survey questions that are most relevant to the user's query by considering:
        
        1. Entity matching: Identify key entities in the query (e.g., people, products, services, processes, experiences) and prioritize questions about those specific entities.
        - Example: If the query mentions a specific person, prioritize questions about individual performance or characteristics.
        - Example: If the query is about a product or service, prioritize questions about features, quality, or satisfaction.
        
        2. Intent alignment: Determine what the user is trying to learn or evaluate, and select questions that address that intent.
        - Example: If the query suggests the user wants feedback on performance, prioritize evaluation questions.
        - Example: If the query suggests the user wants information about preferences, prioritize questions about likes/dislikes.
        
        3. Contextual relevance: Consider the broader context implied by the query, not just explicit keywords.
        - Example: A query about a "manager" suggests interest in leadership, communication, and decision-making.
        - Example: A query about a "checkout process" suggests interest in user experience and efficiency.
        
        4. Question diversity: Include a mix of question types to provide comprehensive feedback while staying relevant to the query focus.
        
        Return the selected questions in this JSON format:
        ```json
        {{
        "selected_questions": [
            {{
            "question_text": "Selected survey question",
            "entity_match": "Selected entity",
            "reasoning": "Reason for selection"
            }},
            // Additional questions...
        ]
        }}
        ```
        
        Important: Prioritize questions that match the most significant entities and intents in the query, even if they don't share exact keywords.
        """
    
    survey_questions = st.session_state.openai_llm.invoke(relevance_prompt).content
    # Add processing logic to process JSON output
    try:
        clean_json = survey_questions.replace('```json', '').replace('```', '').strip()
        survey_data = json.loads(clean_json)
        return [q["question_text"] for q in survey_data["selected_questions"]]
    except json.JSONDecodeError:
        print("Error parsing JSON response")
        return []

def find_exact_matches_intersection(query):
    """
    Find exact matches between result['content'] from vector_search() 
    and survey_questions from query_search() based on their IDs (e.g., A2, A4).

    Args:
    - search_contents: List of strings from result['content'].
    - survey_questions: List of strings (survey questions).

    Returns:
    - matches: A list of strings that are similar between search_contents and survey_questions.
    """
    matches = []

    search_contents = hybrid_search(query, top_k=5)
    print("Search content:", search_contents)
    survey_questions = query_search(query)
    print("LLM response for survey:", survey_questions)

    # Create sets for more efficient comparison
    search_set = set(search_contents)
    survey_set = set(survey_questions)
    
    # Find the intersection of both sets
    matches = list(search_set.intersection(survey_set))
    print(matches)
    
    return matches

