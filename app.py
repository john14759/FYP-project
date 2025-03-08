import streamlit as st

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def logout():
    st.session_state.authenticated = False
    for key in list(st.session_state.keys()): 
        del st.session_state[key]
    st.rerun()

login_signup_page = st.Page("login_signup_page.py", title = "Login/Signup", icon="🔑")
chatbot_main_page = st.Page("main_page.py", title = "NTU Chatbot Helper", icon="🤖", default=True)
survey_gen_page = st.Page("survey_generator_main_page.py", title = "Survey Generator", icon="🛠️")
survey_vis_page = st.Page("survey_visualisation_page.py", title = "Survey Visualisation", icon="📊")
context_uploader_page = st.Page("context_uploader_page.py", title = "Context Uploader", icon="📝")
logout_page = st.Page(logout, title = "Logout", icon="🚪")

if st.session_state.authenticated:
    pg = st.navigation(
        {
            "Account": [logout_page],
            "Chat": [chatbot_main_page],
            "Tools": [survey_gen_page, context_uploader_page, survey_vis_page],
        }
    )
else:
    pg = st.navigation([login_signup_page])

pg.run()