import streamlit as st



st.title("🤖 How to Use EstiMate - Your Guesstimate Interview Assistant")
st.write("""
    Welcome to the Guesstimate Interview Assistant. This app is designed to simulate a guesstimate interview, where you can practice estimating various values based on real-world problems.

    **Steps to use the app:**

    1. **Enter API Key**: In the sidebar, you need to provide an API key from Anthropic for the chatbot to function. This key allows the app to interact with the AI model.
    2. **Start a New Interview**: Click the "Start New Interview" button to begin. You will be presented with a random estimation problem.
    3. **Provide Your Approach**: The interviewer (AI) will ask you to provide your approach for estimating the problem. You can interact with the chatbot by typing your responses in the text input box.
    4. **Get Feedback**: After you’ve completed your approach, you can request feedback on your methodology. The app will evaluate your performance across different criteria.
    5. **Review Results**: After the evaluation, a performance score will be shown. You will also get detailed feedback, including strengths and areas for improvement in your approach.
    
    Happy practicing and improving your estimation skills!
    """)