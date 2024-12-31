import streamlit as st
from datetime import datetime
import plotly.graph_objects as go
#import pyttsx3
import anthropic
import json
from typing import List, Dict
import random
import time
import os
from fpdf import FPDF



#######################################################################################
## Chatbot Class
class GuesstimateChatbot:
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.interview_data = self.load_interview_data("interview_with_context.json")
        self.conversation_history = []
        self.evaluation_criteria = [
            "Structured Approach",
            "Logical Assumptions",
            "Segmentation Strategy",
            "Mathematical Accuracy",
            "Context Awareness"
        ]
        
        # Initialize system prompt
        self.system_prompt = self.create_system_prompt()

   
    def load_interview_data(self, file_path: str) -> Dict:
        """Load and parse interview data from JSON file"""
        with open(file_path, 'r') as f:
            return json.load(f)
    # def load_interview_data(self, input_data) -> Dict:
    #     """
    #     Load and parse interview data.
    #     Accepts either a JSON string or a Python dictionary.
    #     """
    #     if isinstance(input_data, str):  # If input is a JSON string
    #         return json.load(input_data)
    #     elif isinstance(input_data, dict):  # If input is already a dictionary
    #         return input_data
    #     else:
    #         raise ValueError("Invalid input: expected a JSON string or a dictionary.")
     
    def create_system_prompt(self) -> str:
        """Create system prompt for guesstimate interviews"""
        prompt = """You are an expert interviewer specializing in guesstimate questions. Your role is to:

Filters that can be used in problem for approaching problem :

   - Demographics: Age, gender, income level 
   - Geography: City, region, urban vs. rural 
   - Behavior: Usage frequency, product preference, online vs. offline activity 
   - Socioeconomic factors: Education level, occupation
   - Population segmentation
   - Regional variations
   - Income levels
   - Behavioral patterns
   - Seasonal factors


Follow these guidelines:
1. Start with a clear problem statement.
2. Let Candidate Ask clarifying questions about their methodology. You will not give suggestions on clarifying questions , let them ask their own question.
3. Give Only Relevant , Shorter and required answers to clarifying Questions, nothing like -That's a good clarifying question , just give answer, Keep Answers/Clarifying questions around India Only wherver region/ Place not mentioned.
4. Once Clarifying Questions are done, candidate will start his/her approach.
5. Ask or Challenge with Relevant Questions for their assumptions,  calculations, reasoning and filters for segementation they are using,  If necessary.
6. Don't Suggest Next Filters of calculations, Let candidate do their own thing.
7. Once Candidate is done, You will Give review of their approach - the mistakes in assumptions , the filters that they missed and Improvements that could be done.


Example interview patterns from real interviews -:
"""
        # Add example exchanges from the training data
        for interview in self.interview_data['interviews'][:2]:
            prompt += f"\nExample for {interview['topic']}:\n"
            for exchange in interview['exchanges'][:20]:
                prompt += f"{exchange['role'].title()}: {exchange['content']}\n"
        
        return prompt
    
    def select_problem(self) -> str:
        """Select a random problem statement or create a new one From following, You don't have to necessarily choose these , you can make on your own also"""
        return random.choice(self.interview_data['problem_statements'])
    
    def start_interview(self) -> str:
        """Start a new interview with a problem statement"""
        self.conversation_history = []
        self.current_problem = self.select_problem()
        return f"Your problem statement is to {self.current_problem}. Please provide your approach to estimate this value."
    
    def conduct_interview(self, candidate_response: str) -> str:
        """Conduct one turn of the guesstimate interview"""
        
        # Add candidate's response to history
        self.conversation_history.append({
            "role": "user",
            "content": candidate_response
        })
        
        # Create messages for API call - update format
        messages = []
        
        # Add current problem context if exists
        if self.current_problem:
            messages.append({
                "role": "assistant",
                "content": f"Current estimation problem: {self.current_problem}"
            })
        
        # Add conversation history
        messages.extend([
            {"role": "user" if msg["role"] == "user" else "assistant", "content": msg["content"]}
            for msg in self.conversation_history
        ])
        
        # Get response from Claude - note the updated API format
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=messages,
            system=self.system_prompt,  # system is now a separate parameter
            max_tokens=1024,
            temperature=0.7
        )
        
        # Add Claude's response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": response.content[0].text
        })
        
        return response.content[0].text
    
    def evaluate_candidate(self) -> Dict:
        """Evaluate the candidate's guesstimate approach"""
        evaluation_prompt = """Based on the interview conversation, please evaluate:
            1. 'structure': Did they break down the problem logically. Rate out of 5?
            2. 'assumptions': Were assumptions reasonable and India-specific. Rate out of 5?
            3. 'segmentation': How well did they segment the problem. Rate out of 5?
            4. 'math': Were calculations logical and error-free. Rate out of 5?
            5. 'context': Did they consider context of the problem appropriately. Rate out of 5?
            6. 'filters_missed': (they missed and needed to added in string)
            6. 'key_strengths': (Good poitns in the approach in string) 
            7. 'areas_for_improvement': (Areas in approach to improve in string)
            Keep names of 'Key'  like 'structure', 'assumptions', etc..  in JSON as above only. Format as valid JSON string only. FORMAT AS VALID JSON ONLY. I am Saying this again: RETURN AS JSON FORMAT STRING. """
        
        messages = [
            {
                "role": "user",
                "content": f"Problem: {self.current_problem}\n\nInterview transcript: {json.dumps(self.conversation_history)}\n\n{evaluation_prompt}"
            }
        ]
        
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=messages,
            system=self.system_prompt,  # system as separate parameter
            max_tokens=1024,
            temperature=0.3
        )
        evaluation_json={}
        try:
            evaluation_json=json.loads(response.content[0].text)
            return evaluation_json
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            print(f"Error parsing JSON: {e}")
            return None

    





# def response_generator(response):
#     for sentence in response.split("."):
#         yield sentence + " "
#         SpeakText(sentence)

def response_generator(response):
    for sentence in response.split("."):
        for word in sentence.split(" "):  # Corrected 'split'
            yield word + " "  # Yield each word with a space
            time.sleep(0.05)
        #SpeakText(sentence)  # Speak the entire sentence after yielding words


# # Function to convert text to speech
# def SpeakText(command):
#     # Initialize the engine
#     engine = pyttsx3.init()
#     engine.say(command) 
#     engine.runAndWait()

def save_interview(conversation_history: list, evaluation: dict):
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    folder_path = "interview_scripts"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        
    file_name = f"interview_{timestamp}.txt"
    file_path = os.path.join(folder_path, file_name)
    
    with open(file_path, "w") as file:
        file.write("Guesstimate Interview\n")
        file.write(f"Datetime: {timestamp}\n\n")
        for msg in conversation_history:
            role = "Interviewer" if msg["role"] == "assistant" else "Candidate"
            file.write(f"{role}: {msg['content']}\n")
        file.write("\nEvaluation:\n")
        file.write(json.dumps(evaluation, indent=2))
    
    return file_path



def download_interview_transcript(conversation_history: list, evaluation: dict) -> str:
    """
    Generate a downloadable transcript of the conversation history as a PDF file.
    """
    # Create PDF instance
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Title
    pdf.set_font("Arial", style="B", size=16)
    pdf.cell(200, 10, txt="Guesstimate Interview Transcript", ln=True, align='C')
    pdf.ln(10)
    
    # Date and Time
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Date and Time: {timestamp}", ln=True)
    pdf.ln(10)
    
    # Conversation History
    pdf.set_font("Arial", style="B", size=12)
    pdf.cell(0, 10, txt="Conversation History:", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", size=12)
    for msg in conversation_history:
        role = "Interviewer" if msg["role"] == "assistant" else "Candidate"
        pdf.multi_cell(0, 10, txt=f"{role}: {msg['content']}")
        pdf.ln(2)
    
    # Evaluation Section
    pdf.ln(10)
    pdf.set_font("Arial", style="B", size=12)
    pdf.cell(0, 10, txt="Evaluation Results:", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=json.dumps(evaluation, indent=2))
    
    # Save the PDF
    file_name = f"interview_transcript_{timestamp.replace(':', '-').replace(' ', '_')}.pdf"
    pdf.output(file_name)
    return file_name
    
    

def create_score_bar_graph(scores):
    fig = go.Figure(data=[
        go.Bar(
            x=list(scores.keys()),
            y=list(scores.values()),
            marker_color='rgb(26, 118, 255)',
            text=[f"{score}/10" for score in scores.values()],
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title='Interview Performance Scores',
        yaxis=dict(
            title='Score',
            range=[0, 10],  # Set y-axis range from 0 to 10
            tickmode='linear',
            tick0=0,
            dtick=1,  # Show all integer ticks from 0 to 10
        ),
        xaxis_title='Criteria',
        showlegend=False,
        height=400,
        margin=dict(t=50, l=50, r=50, b=50)
    )
    
    return fig


def main():
    st.set_page_config(page_title="EstiMate", layout="wide")

    
        
    
    st.title("🤖 Guesstimate Interview Assistant")
    
    # Initialize session state
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'interview_started' not in st.session_state:
        st.session_state.interview_started = False
    if 'evaluation_done' not in st.session_state:
        st.session_state.evaluation_done = False
    if 'chatbot' not in st.session_state:
        st.session_state.chatbot = None
    st.page_link("pages/How To Use.py",label="How To Use EstiMate",icon="🤖")    
    # Sidebar for API key and controls
    with st.sidebar:
        st.header("Configuration")
        api_key = st.text_input("Enter Anthropic API Key:", type="password")
        #interview_data_path = st.text_input("Interview Data Path:", value="interview_with_context.json")
        interview_data_path="interview_with_context.json"
        
        if st.button("Start New Interview", disabled=not api_key):
            #st.session_state.chatbot = GuesstimateChatbot(api_key, interview_data_path)
            st.session_state.chatbot = GuesstimateChatbot(api_key)
            st.session_state.messages = []
            st.session_state.interview_started = True
            st.session_state.evaluation_done = False
            
            # Start interview and get initial problem
            initial_message = st.session_state.chatbot.start_interview()
            st.session_state.messages.append({"role": "assistant", "content": initial_message})
            
        if st.button("End Interview & Evaluate", disabled=not st.session_state.interview_started or st.session_state.evaluation_done):
            evaluation = st.session_state.chatbot.evaluate_candidate()
            st.session_state.evaluation = evaluation
            st.session_state.evaluation_done = True
            file_path = save_interview(st.session_state.messages, evaluation)
            st.success(f"Interview saved to: {file_path}")

        
    
    # Main chat interface
    if st.session_state.interview_started:
        # Display chat messages
        for message in st.session_state.messages:
            role = "🤖 Interviewer" if message["role"] == "assistant" else "👤 Candidate"
            with st.chat_message(message["role"]):
                st.write(f"{message['content']}")
        
        # Chat input
        if not st.session_state.evaluation_done:
            user_input = st.chat_input("Your response...")
            if user_input:
                # Add user message
                st.session_state.messages.append({"role": "user", "content": user_input})
                with st.chat_message("user"):
                    st.write(f"{user_input}")
                # Get interviewer response
                with st.spinner("Interviewer is thinking..."):
                    response = st.session_state.chatbot.conduct_interview(user_input)
                    #response=f"ECHO ECHO : {user_input}"
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    with st.chat_message("assistant"):
                        st.write_stream(response_generator(response))

                st.rerun()
        
        # Display evaluation
        if st.session_state.evaluation_done:
            st.header("Interview Evaluation")


            try:
                

                if st.session_state.evaluation_done and "form_submitted" not in st.session_state:
                    st.subheader("Please Fill Out the Feedback Form Before Viewing Your Results")

                    with st.form("feedback_form"):
                        first_name = st.text_input("First Name")
                        last_name = st.text_input("Last Name")
                        college_name = st.text_input("Name of College")
                        year_of_passing = st.text_input("Year of Passing")
                        knowledge_level = st.selectbox("What is your current level of knowledge?", ["Beginner", "Intermediate", "Advanced"])
                        session_feedback = st.text_area("How did you feel about the session?")
                        expected_score = st.slider("What score out of 10 do you expect in this interview?", 0, 10, 5)
                        overall_experience = st.text_area("How was your experience in the interview?")
                        reuse=st.selectbox("Will you use future versions of this app?", ["Yes", "No"])
        
                        submitted = st.form_submit_button("Submit Feedback")

                if submitted:
            # Save user responses
                    feedback_data = {
                        "first_name": first_name,
                        "last_name": last_name,
                        "college_name": college_name,
                        "year_of_passing": year_of_passing,
                        "knowledge_level": knowledge_level,
                        "session_feedback": session_feedback,
                        "expected_score": expected_score,
                        "overall_experience": overall_experience,
                        "reuse": reuse,
                    }

            # Save feedback data as a JSON file
                    feedback_file_path = os.path.join("feedback_data", f"feedback_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.json")
                    os.makedirs("feedback_data", exist_ok=True)
                    with open(feedback_file_path, "w") as feedback_file:
                        json.dump(feedback_data, feedback_file,indent=4)
            
                    st.success("Thank you for your feedback! Your responses have been recorded.")
                    st.session_state.form_submitted = True

                if st.session_state.evaluation_done and st.session_state.get("form_submitted"):
                    st.header("Interview Evaluation Results") 
                    eval_data = st.session_state.get("evaluation", {})   
                
                # Ensure eval_data is a dictionary
                    if not isinstance(eval_data, dict):
                        raise ValueError("Evaluation data is not in the expected format.")

                # Convert scores to a 10-point scale (assuming original scores were out of 5)
                    scores = {
                        "Structure": eval_data.get("structure", 0) * 2,
                        "Assumptions": eval_data.get("assumptions", 0) * 2,
                        "Segmentation": eval_data.get("segmentation", 0) * 2,
                        "Math": eval_data.get("math", 0) * 2,
                        "Context": eval_data.get("context", 0) * 2,
                    }

                # Display bar graph
                    st.plotly_chart(create_score_bar_graph(scores), use_container_width=True)

                # Display detailed feedback
                    st.subheader("Detailed Feedback")
                    st.write("**Missed Filters:**")
                    st.write(eval_data.get("filters_missed", "No data available"))
                    st.write("**Key Strengths:**")
                    st.write(eval_data.get("key_strengths", "No data available"))
                    st.write("**Areas for improvement**")
                    st.write(eval_data.get("areas_for_improvement", "No data available"))
                else:
                    st.write("Please submit the feedback form first to view your results.")    
                

            except KeyError as e:
                st.error(f"Missing key in evaluation data: {e}")
            except ValueError as e:
                st.error(f"Invalid evaluation data: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

        if st.session_state.evaluation_done:
            file_name = download_interview_transcript(st.session_state.messages,st.session_state.evaluation)
            
            with open(file_name, "rb") as pdf_file:
                pdf_data = pdf_file.read()

            st.download_button(
                label="Download Your Interview Transcript",
                data=pdf_data,
                file_name=file_name,
                mime="application/pdf"
            )        

            # eval_data = st.session_state.evaluation
            
            # # Convert scores to 10-point scale (assuming original scores were out of 5)
            # scores = {
            #     "Structure": eval_data.get("structure", 0) * 2,
            #     "Assumptions": eval_data.get("assumptions", 0) * 2,
            #     "Segmentation": eval_data.get("segmentation", 0) * 2,
            #     "Math": eval_data.get("math", 0) * 2,
            #     "Context": eval_data.get("context", 0) * 2
            # }
            
            # # Display bar graph
            # st.plotly_chart(create_score_bar_graph(scores), use_container_width=True)
            
            # # Display detailed feedback
            # st.subheader("Detailed Feedback")
            # st.write("**Missed Filters:**")
            # st.write(eval_data.get("filters_missed", ""))
            # st.write("**Key Strengths:**")
            # st.write(eval_data.get("key_strengths", ""))
            # st.write("**Areas for improvement**")
            # st.write(eval_data.get("areas_for_improvement", ""))

if __name__ == "__main__":
    main()