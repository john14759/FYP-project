import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

@st.cache_resource(show_spinner=False)
def get_db_connection():
    """Cache the database connection"""
    return MongoClient(os.environ['PYMONGO_CONNECTION_STRING'])

@st.cache_data(ttl=600, show_spinner="Loading survey data...")
def get_survey_data():
    """Cache survey data with 5 minute freshness"""
    client = get_db_connection()
    return list(client['chatbot']['surveys'].find({}))

# Create page layout
st.title("Survey Results Dashboard")

# Get cached data
survey_data = get_survey_data()

if not survey_data:
    st.warning("No survey data available!")
else:
    # Get all unique questions across surveys
    all_questions = list(set([q for doc in survey_data for q in doc['questions']]))
    
    # Add summary statistics
    st.header("Summary Statistics:")
    st.write("Total number of responses:", len(survey_data))
    st.write("Unique questions asked across surveys:", len(all_questions))

    # Convert to DataFrame with actual question text
    df = pd.DataFrame([{
        **{'User': doc['user']},
        **{question: doc['answers'][i] for i, question in enumerate(doc['questions'])}
    } for doc in survey_data])

    # Ensure consistent column order (all unique questions as columns)
    df = df.reindex(columns=['User'] + all_questions, fill_value="No Response")

    # Display raw survey data with actual question text
    st.header("Raw Survey Data")
    st.dataframe(df)

    # Create visualizations
    st.header("Question-wise Analysis")
    
    for question in all_questions:
        # Find which index this question had in different surveys
        answers = []
        for doc in survey_data:
            try:
                idx = doc['questions'].index(question)
                answers.append(doc['answers'][idx])
            except ValueError:
                continue
        
        if answers:
            with st.expander(f"{question}"):
                col1, col2 = st.columns(2)
                
                # Bar chart
                with col1:
                    st.subheader("Answer Distribution")
                    answer_counts = pd.Series(answers).value_counts()
                    st.bar_chart(answer_counts)
                
                # Pie chart
                with col2:
                    st.subheader("Percentage Breakdown")
                    fig, ax = plt.subplots()
                    ax.pie(answer_counts, 
                           labels=answer_counts.index,
                           autopct='%1.1f%%')
                    st.pyplot(fig)

