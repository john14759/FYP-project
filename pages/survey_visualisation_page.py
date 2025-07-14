import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import numpy as np

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


def get_all_available_questions():
    # Fetch all survey data
    survey_data = get_survey_data()

    # Loop through the survey data to find the `all_questions` entry
    for survey in survey_data:
        if 'all_questions' in survey:
            return survey['all_questions']
    return None  # Return None if no 'all_questions' field is found

# Create page layout
st.title("Survey Results Dashboard:")
st.divider()

# Get cached data
survey_data = get_survey_data()

if not survey_data:
    st.warning("No survey data available!")
else:
    # Process data
    all_questions = list(set([q for doc in survey_data if 'questions' in doc for q in doc['questions']]))

    sorted_questions = sorted(all_questions)  # For consistent ordering
    
    # Create answer distribution dataframe
    dist_data = []
    for question in sorted_questions:
        answers = []
        for doc in survey_data:
            if 'questions' in doc and question in doc['questions']:
                idx = doc['questions'].index(question)
                answers.append(doc['answers'][idx])
        
        # Create distribution counts
        answer_counts = pd.Series(answers).value_counts().reindex(range(1, 6), fill_value=0)
        dist_data.append({
            'Question': question,
            **{f'Rating {i}': answer_counts[i] for i in range(1, 6)}
        })
    
    df_dist = pd.DataFrame(dist_data)

    # Summary statistics
    st.header("Summary Statistics")
    st.info("📊 High-level overview of response volume and question diversity")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Responses", sum(len(doc.get('answers', [])) for doc in survey_data))
    with col2:
        st.metric("Unique Questions", len(sorted_questions) -1)
    st.divider()

    st.header("Individual User Completeness:")
    st.info("📋 Completeness overview for each user: ✔️ = answered, ❌ = not yet answered")

    # Get all available questions from database
    all_questions_list = get_all_available_questions()
    if not all_questions_list:
        st.error("Could not load question list from database")
        st.stop()

    # Create a dictionary to aggregate user responses
    user_responses = {}

    # Process all survey documents
    for doc in survey_data:
        if 'user' not in doc or 'questions' not in doc or 'answers' not in doc:
            continue
        
        user = doc['user']
        if user not in user_responses:
            user_responses[user] = {}
        
        # Add all question-answer pairs for this submission
        for q, a in zip(doc['questions'], doc['answers']):
            user_responses[user][q] = a

    # Create one row per question
    data = []
    for question in all_questions_list:
        row = {'Question': question}
        for user in user_responses:
            if question in user_responses[user]:
                row[user] = '✔️'  # Mark as answered
            else:
                row[user] = '❌'  # Mark as not answered
        data.append(row)

    df_raw = pd.DataFrame(data)

    # Reorder columns so that 'Question' is the first column
    df_raw = df_raw[['Question'] + list(user_responses.keys())]

    # Style the dataframe
    styled_df = df_raw.style.applymap(lambda x: 'color: #d62728' if x == '❌' else 'color: #2ca02c')

    # Display with optimized formatting
    st.dataframe(
        styled_df,
        use_container_width=True,
        column_config={
            "Question": st.column_config.TextColumn(
                "Survey Question",
                width="medium"
            ),
            **{user: st.column_config.Column(
                user,
                help="Shows ✔️ if answered or ❌ if not",
                width="small"
            ) for user in user_responses}
        }
    )

    st.divider()

    st.header("Survey Submission Timeline")
    st.info("🕒 Interactive visualization of response patterns over time. Use slider/buttons to explore different time ranges")

    # Process timestamp data
    timeline_data = []
    for doc in survey_data:
        if 'timestamp' in doc:  # Ensure document has timestamp
            try:
                ts = pd.to_datetime(doc['timestamp'])
                timeline_data.append({
                    'User': doc['user'],
                    'Timestamp': ts
                })
            except (TypeError, ValueError):
                pass  # Skip invalid timestamps

    if not timeline_data:
        st.warning("No timestamp data available!")
    else:
        # Create timeline dataframe
        df_timeline = pd.DataFrame(timeline_data)
        
        # Create interactive timeline plot
        fig = px.scatter(
            df_timeline,
            x='Timestamp',
            y='User',
            color='User',
            labels={'Timestamp': 'Submission Time', 'User': 'Respondent'},
            category_orders={"User": sorted(df_timeline['User'].unique())},
            color_discrete_sequence=px.colors.qualitative.Plotly
        )
        
        # Add hover formatting and annotations
        fig.update_traces(
            marker=dict(size=10, line=dict(width=2, color='DarkSlateGrey')),
            hovertemplate="<b>%{y}</b><br>%{x|%Y-%m-%d %H:%M:%S}<extra></extra>"
        )
        
        # Add time range selector
        fig.update_layout(
            xaxis=dict(
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1d", step="day", stepmode="backward"),
                        dict(count=7, label="1w", step="day", stepmode="backward"),
                        dict(count=1, label="1m", step="month", stepmode="backward"),
                        dict(step="all")
                    ])
                ),
                rangeslider=dict(visible=True),
                type="date"
            ),
            height=600,
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
        st.divider()

    # Get the accent color from the Reds color scale
    colors = px.colors.sequential.Reds[::-1]  # Reverse for better rating visibility
    accent_color = colors[5]  # Use the darkest red as accent

    # Create shortened questions for display
    df_dist['Short Question'] = df_dist['Question'].apply(lambda q: q[:40] + '...' if len(q) > 40 else q)

    # Create a figure with a single subplot
    fig = go.Figure()

    # Add each rating as a separate trace
    for i, rating in enumerate(range(5, 0, -1)):
        fig.add_trace(go.Bar(
            y=df_dist['Short Question'],
            x=df_dist[f'Rating {rating}'],
            name=f'Rating {rating}',
            orientation='h',
            marker_color=colors[i],
            text=df_dist[f'Rating {rating}'],
            textposition='inside',
            texttemplate='%{text}'
        ))

    # Create a custom hover template using the 'hovertemplate' property
    fig.update_traces(
        hoverinfo='none',
        hovertemplate=None
    )

    # Create a custom hover function with styling
    def create_hover_template():
        """Create a styled custom hover template that shows the full question once, followed by ratings."""
        question_dict = {short: full for short, full in zip(df_dist['Short Question'], df_dist['Question'])}
        
        # Define rating colors to match your legend
        rating_colors = {
            1: "#FF8C75",  # Light red for Rating 1
            2: "#E74C3C",  # Medium-light red for Rating 2
            3: "#C0392B",  # Medium red for Rating 3
            4: "#A93226",  # Medium-dark red for Rating 4
            5: "#800000"   # Dark red for Rating 5
        }
        
        hover_template = []
        for idx, question in enumerate(df_dist['Short Question']):
            # Style the question to stand out
            hover_data = f"<br><b style='color:{accent_color} ; font-size:16px'>Question: </b>{question_dict[question]}<br><br>"
            
            # Add rating information with styling that matches legend colors
            for rating in range(1, 6):
                value = df_dist.iloc[idx][f'Rating {rating}']
                color = rating_colors[rating]
                # Add a colored square marker to match the legend style
                hover_data += f"<br><span style='color:{color};font-size:20px;'>■</span> <span style='color:#FAFAFA;'>Rating {rating}:</span> {value}<br>"
            
            hover_template.append(hover_data)
        
        return hover_template

    # Create a hover template for each question
    hover_templates = create_hover_template()

    # Add an invisible trace that will be used for the custom hover
    fig.add_trace(go.Scatter(
        x=[0] * len(df_dist),
        y=df_dist['Short Question'],
        mode='markers',
        marker=dict(size=0, opacity=0),
        hoverinfo='text',
        hovertext=hover_templates,
        showlegend=False
    ))

    # Update the layout with theme-matched styling
    fig.update_layout(
        barmode='stack',
        height=600 + len(df_dist) * 20,
        showlegend=True,
        xaxis_title="Number of Responses",
        yaxis_title="Questions",
        hovermode='y unified',
        hoverlabel=dict(
            bgcolor="#0E1117",
            font_color="#FAFAFA",
            font_size=12,
            align="left",
        ),
    )

    # Display the chart
    st.header("Answer Distribution Overview")
    st.info("📈 Stacked rating breakdown per question. Hover for detailed counts, click legend to filter ratings")
    st.plotly_chart(fig, use_container_width=True)
    st.divider()

    # Detailed question analysis
    st.header("Detailed Question Analysis")
    st.info("🔍 Click each question to expand detailed response metrics. Switch between distribution and percentage views")
    for question in sorted_questions:
        with st.expander(f"{question}", expanded=False):
            # Get answers for current question
            answers = []
            for doc in survey_data:
                if 'questions' in doc and question in doc['questions']:
                    idx = doc['questions'].index(question)
                    answers.append(doc['answers'][idx])
            
            if not answers:
                st.write("No responses for this question")
                continue
                
            # Create interactive tabs
            tab1, tab2 = st.tabs(["Distribution", "Breakdown"])
            
            with tab1:
                # Horizontal stacked bar (single question)
                fig1 = px.bar(
                    x=[f'Rating {i}' for i in range(1, 6)],
                    y=[(pd.Series(answers) == i).sum() for i in range(1, 6)],
                    color=[f'Rating {i}' for i in range(1, 6)],
                    color_discrete_sequence=px.colors.sequential.Reds[::-1],
                    labels={'x': 'Rating', 'y': 'Count'},
                    title="Response Distribution"
                )
                st.plotly_chart(fig1, use_container_width=True, key=f"dist_{question}")

            
            with tab2:
                # Interactive pie chart
                fig2 = px.pie(
                    names=[f'Rating {i}' for i in pd.Series(answers).value_counts().index],
                    values=pd.Series(answers).value_counts().values,
                    hole=0.3,
                    title="Response Breakdown",
                    color=[f'Rating {i}' for i in pd.Series(answers).value_counts().index],  # Apply colors based on ratings
                    color_discrete_sequence=px.colors.sequential.Reds[::-1]  # Shades of red (reverse order for better visibility)
                )
                fig2.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig2, use_container_width=True, key=f"pie_{question}")
    


