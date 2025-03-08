from response import *
from init import *
from conversation_display import *
from survey import *
from survey_gen import *

st.set_page_config(page_title="NTU Teaching Assistant Chatbot", layout="wide")

# Check if initialization flag exists in session state, if not, initialize
if 'initialised' not in st.session_state:
    init()  # Run only once
    st.session_state.initialised = True

main_chatbot_interface()
st.session_state.conversation

    






