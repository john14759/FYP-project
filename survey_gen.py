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
    Analyze the user's question below and identify the key themes, intent, and context. From the predefined survey question list {all_questions}, select and rank the top 3-5 most relevant questions to ask the user next. Prioritize questions that:

    1. Directly address the user’s explicit or implicit needs,
    2. Align with the topic’s urgency/depth (e.g., factual vs. exploratory),
    3. Complement the conversation flow (e.g., follow-up, clarification),
    4. Balance open-ended and closed-ended formats based on the query’s complexity.

    For each selected question, provide a brief rationale. Exclude redundant or generic questions.

    User Query: {query}

    Response Format:
    ```json
    {{
      "selected_questions": [
        {{
          "rank": 1,
          "question": "Selected survey question",
          "reason": "Explanation of relevance to the query",
          "type": "open/closed"
        }},
        ...
      ]
    }}
    ```
    """
    
    survey_questions = st.session_state.openai_llm.invoke(relevance_prompt).content
    # Add processing logic to process JSON output
    try:
        clean_json = survey_questions.replace('```json', '').replace('```', '').strip()
        survey_data = json.loads(clean_json)
        return [q["question"] for q in survey_data["selected_questions"]]
    except json.JSONDecodeError:
        print("Error parsing JSON response")
        return []

def find_exact_matches_by_id(query):
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

