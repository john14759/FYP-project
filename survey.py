import streamlit as st
import time

def show_survey():

    survey_container = st.container()

    with survey_container:
                st.markdown("""
                    <div class="survey-container">
                        <h2>Quick Survey</h2>
                        <p>Help us improve the course logistics and coordination by completing this brief survey.</p>
                    </div>
                """, unsafe_allow_html=True)

                progress = len(st.session_state.survey_responses)
                total = len(st.session_state.survey_questions)

                if total > 0: #there was an error where total is 0
                    st.progress(progress/total)

                    if progress < total:

                        full_question = st.session_state.survey_questions[progress]
                        display_question = full_question  

                        # Check if the question starts with a pattern like "D7: " 
                        if ': ' in full_question and full_question[0].isalpha() and full_question[1:].split(':', 1)[0].isdigit():
                            # Split at the first colon and space
                            display_question = full_question.split(': ', 1)[1]
                        
                        st.info(f"Q{progress + 1}: {display_question}")

                        # Define rating labels
                        ratings = ["Very Poor", "Poor", "Average", "Good", "Very Good"]

                        # Create 5 columns for the buttons
                        cols = st.columns(5)
                        for i, (col, label) in enumerate(zip(cols, ratings), start=1):
                            with col:
                                if st.button(
                                    label,
                                    type="primary",  # To highlight the button on hover
                                    key=f"survey_btn_{i}",
                                    use_container_width=True,
                                    on_click=on_survey_input_change,
                                    args=(i,)  # Pass the rating value to the callback
                                ):
                                    pass  # The logic is handled in the callback
                    else:
                        st.success("Returning to chat...")
                        st.toast("Thank you for your feedback!", icon="👍")
                        complete_survey()
                        survey_container.empty()
                        time.sleep(3)
                        st.rerun()
                    

def on_survey_input_change(rating):
    if len(st.session_state.survey_responses) < len(st.session_state.survey_questions):
        st.session_state.survey_responses.append(rating)

def complete_survey():

    st.session_state.survey_shown = False

    # Retrieve survey questions and responses from session state
    if 'survey_questions' in st.session_state and 'survey_responses' in st.session_state:
        survey_data = {
            "user": st.session_state.get("username", "Anonymous"),  # Optionally store user identity
            "questions": st.session_state.survey_questions,
            "answers": st.session_state.survey_responses
        }
        
        # Get the client from session state
        sql_client = st.session_state.sql_client

        chatbot_db = sql_client['chatbot']  # Use the chatbot database
        surveys_collection = chatbot_db['surveys']  # You can create a 'surveys' collection
        
        surveys_collection.insert_one(survey_data)  # Insert the survey data

    #Then, clean up session state
    if 'survey_questions' in st.session_state:
        #del st.session_state['survey_questions']
        st.session_state['survey_questions'] = []

    if 'survey_responses' in st.session_state:
        #del st.session_state['survey_responses']
        st.session_state['survey_responses'] = []