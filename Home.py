import streamlit as st
from datetime import datetime
import plotly.graph_objects as go
import json
from typing import Dict
import random
import time
import os
from fpdf import FPDF
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from groq import Groq

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="EstiMate | Guesstimate Interview",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stChatMessage { border-radius: 12px; margin-bottom: 8px; }
    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        text-align: center;
        margin-bottom: 10px;
    }
    .metric-card h3 { font-size: 28px; color: #1a73e8; margin: 0; }
    .metric-card p { font-size: 12px; color: #888; margin: 0; }
    .problem-banner {
        background: linear-gradient(135deg, #1a73e8, #0d47a1);
        color: white;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 20px;
        font-size: 17px;
        font-weight: 500;
    }
    .tip-box {
        background: #e8f5e9;
        border-left: 4px solid #43a047;
        border-radius: 6px;
        padding: 12px 16px;
        font-size: 13px;
        color: #2e7d32;
        margin-bottom: 14px;
    }
    .eval-header {
        background: linear-gradient(135deg, #0d47a1, #1565c0);
        color: white;
        border-radius: 12px;
        padding: 18px 24px;
        margin-bottom: 20px;
        text-align: center;
    }
    .score-overall {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        text-align: center;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# GOOGLE SHEETS CONNECTION
# ─────────────────────────────────────────────
@st.cache_resource
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_existing_data():
    try:
        conn = get_connection()
        data = conn.read(worksheet="data", usecols=list(range(10)))
        return data.dropna(how='all')
    except Exception:
        return pd.DataFrame()

# ─────────────────────────────────────────────
# GROQ MODEL
# ─────────────────────────────────────────────
GROQ_MODEL = "llama-3.3-70b-versatile"

# ─────────────────────────────────────────────
# DONE SIGNAL DETECTION
# ─────────────────────────────────────────────
DONE_PHRASES = [
    "i'm done", "i am done", "im done", "that's my answer",
    "that is my answer", "i'm finished", "i am finished",
    "done with my estimate", "my final answer", "my estimate is complete",
    "finished my estimate", "that's my final", "conclude my estimate",
    "end my interview", "submit my answer"
]

def user_signaled_done(text: str) -> bool:
    lowered = text.lower().strip()
    return any(phrase in lowered for phrase in DONE_PHRASES)

# ─────────────────────────────────────────────
# CHATBOT CLASS
# ─────────────────────────────────────────────
class GuesstimateChatbot:

    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.interview_data = self.load_interview_data("interview_with_context.json")
        self.conversation_history = []
        self.current_problem = None
        self.turn_count = 0
        self.max_turns = 20
        self.system_prompt = self.create_system_prompt()

    def load_interview_data(self, file_path: str) -> Dict:
        with open(file_path, 'r') as f:
            return json.load(f)

    def create_system_prompt(self) -> str:
        prompt = """You are an expert interviewer specializing in guesstimate questions for product management and consulting interviews. Your role is to:

Filters that can be used in a problem:
- Demographics: Age, gender, income level
- Geography: City, region, urban vs. rural
- Behavior: Usage frequency, product preference, online vs. offline activity
- Socioeconomic factors: Education level, occupation
- Population segmentation, Regional variations, Income levels
- Behavioral patterns, Seasonal factors

Follow these guidelines strictly:
1. Start with a clear problem statement.
2. Let the candidate ask clarifying questions. Do NOT suggest clarifying questions — let them ask their own.
3. Give only relevant, short, and required answers to clarifying questions. No praise like "That's a good question." Keep answers India-specific wherever region is not mentioned.
4. Once clarifying questions are done, the candidate will start their approach.
5. Challenge their assumptions, calculations, reasoning, and segmentation filters with relevant questions if necessary.
6. Do NOT suggest next filters or calculations. Let the candidate lead.
7. If the candidate says "I'm done" or signals completion, acknowledge it and give a brief closing remark. The evaluation will be handled separately.

IMPORTANT: Be concise. Do not over-explain. Act like a real interviewer — neutral, focused, and direct.

Example interview patterns:
"""
        for interview in self.interview_data['interviews'][:2]:
            prompt += f"\nExample for {interview['topic']}:\n"
            for exchange in interview['exchanges'][:15]:
                prompt += f"{exchange['role'].title()}: {exchange['content']}\n"
        return prompt

    def select_problem(self) -> str:
        return random.choice(self.interview_data['problem_statements'])

    def start_interview(self) -> str:
        self.conversation_history = []
        self.turn_count = 0
        self.current_problem = self.select_problem()
        return (
            f"Your problem statement is: **{self.current_problem}**\n\n"
            "Please begin by asking any clarifying questions you need. "
            "When you've finished your estimate, type **\"I'm done\"**."
        )

    def conduct_interview(self, candidate_response: str) -> str:
        if self.turn_count >= self.max_turns:
            return "TURN_LIMIT_EXCEEDED"

        self.conversation_history.append({
            "role": "user",
            "content": candidate_response
        })

        messages = [{"role": "system", "content": self.system_prompt}]

        if self.current_problem:
            messages.append({
                "role": "assistant",
                "content": f"Problem statement: {self.current_problem}"
            })

        messages.extend(self.conversation_history)

        try:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=1024,
                temperature=0.7,
            )
            reply = response.choices[0].message.content
        except Exception as e:
            reply = f"Error getting response: {str(e)}. Please check your Groq API key."

        self.conversation_history.append({
            "role": "assistant",
            "content": reply
        })

        self.turn_count += 1
        return reply

    def evaluate_candidate(self) -> Dict:
        evaluation_prompt = """Based on the interview conversation, evaluate the candidate and return ONLY a valid JSON object with these exact keys:
{
  "structure": <integer 1-5>,
  "assumptions": <integer 1-5>,
  "segmentation": <integer 1-5>,
  "math": <integer 1-5>,
  "context": <integer 1-5>,
  "filters_missed": "<string describing missed filters>",
  "key_strengths": "<string describing what the candidate did well>",
  "areas_for_improvement": "<string with specific actionable improvements>"
}

Score guidelines:
- 1: Very poor, major issues
- 2: Below average, several issues
- 3: Average, meets basic expectations
- 4: Good, minor issues
- 5: Excellent, no significant issues

Return ONLY the JSON. No explanation, no markdown, no code blocks. Raw JSON only."""

        messages = [
            {"role": "system", "content": "You are a strict evaluator. Return only valid JSON."},
            {
                "role": "user",
                "content": (
                    f"Problem: {self.current_problem}\n\n"
                    f"Transcript:\n{json.dumps(self.conversation_history)}\n\n"
                    f"{evaluation_prompt}"
                )
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=1024,
                temperature=0.2,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown fences if model adds them
            if "```" in raw:
                parts = raw.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    try:
                        return json.loads(part)
                    except Exception:
                        continue
            return json.loads(raw)
        except (json.JSONDecodeError, Exception) as e:
            st.error(f"Evaluation parsing error: {e}")
            return {
                "structure": 3, "assumptions": 3, "segmentation": 3,
                "math": 3, "context": 3,
                "filters_missed": "Could not parse evaluation.",
                "key_strengths": "Could not parse evaluation.",
                "areas_for_improvement": "Could not parse evaluation."
            }


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def response_generator(response: str):
    for word in response.split(" "):
        yield word + " "
        time.sleep(0.03)


def save_interview(conversation_history: list, evaluation: dict) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    folder_path = "interview_scripts"
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"interview_{timestamp}.txt")
    with open(file_path, "w") as f:
        f.write("EstiMate | Guesstimate Interview\n")
        f.write(f"Datetime: {timestamp}\n\n")
        for msg in conversation_history:
            role = "Interviewer" if msg["role"] == "assistant" else "Candidate"
            f.write(f"{role}: {msg['content']}\n\n")
        f.write("\nEvaluation:\n")
        f.write(json.dumps(evaluation, indent=2))
    return file_path


def download_interview_transcript(conversation_history: list, evaluation: dict) -> str:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", style="B", size=18)
    pdf.cell(0, 12, txt="EstiMate | Guesstimate Interview Transcript", ln=True, align='C')
    pdf.ln(4)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pdf.set_font("Arial", size=10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8, txt=f"Generated: {timestamp}", ln=True, align='C')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    pdf.set_font("Arial", style="B", size=12)
    pdf.cell(0, 10, txt="Interview Transcript", ln=True)
    pdf.ln(3)

    for msg in conversation_history:
        role = "Interviewer" if msg["role"] == "assistant" else "Candidate"
        pdf.set_font("Arial", style="B", size=10)
        if role == "Interviewer":
            pdf.set_text_color(26, 115, 232)
        else:
            pdf.set_text_color(67, 160, 71)
        pdf.cell(0, 7, txt=f"{role}:", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.set_text_color(30, 30, 30)
        content = msg['content'].encode('latin1', 'replace').decode('latin1')
        pdf.multi_cell(0, 6, txt=content)
        pdf.ln(3)

    pdf.ln(6)
    pdf.set_font("Arial", style="B", size=12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, txt="Evaluation Results", ln=True)
    pdf.ln(3)
    pdf.set_font("Arial", size=10)

    scores_text = (
        f"Structure:    {evaluation.get('structure', 0) * 2}/10\n"
        f"Assumptions:  {evaluation.get('assumptions', 0) * 2}/10\n"
        f"Segmentation: {evaluation.get('segmentation', 0) * 2}/10\n"
        f"Math:         {evaluation.get('math', 0) * 2}/10\n"
        f"Context:      {evaluation.get('context', 0) * 2}/10\n\n"
        f"Filters Missed:\n{evaluation.get('filters_missed', '')}\n\n"
        f"Key Strengths:\n{evaluation.get('key_strengths', '')}\n\n"
        f"Areas for Improvement:\n{evaluation.get('areas_for_improvement', '')}"
    )
    scores_text = scores_text.encode('latin1', 'replace').decode('latin1')
    pdf.multi_cell(0, 6, txt=scores_text)

    file_name = f"estimate_transcript_{timestamp.replace(':', '-').replace(' ', '_')}.pdf"
    pdf.output(file_name)
    return file_name


def create_score_chart(scores: dict):
    colors = ['#1a73e8' if v >= 7 else '#f4b400' if v >= 5 else '#ea4335' for v in scores.values()]
    fig = go.Figure(data=[
        go.Bar(
            x=list(scores.keys()),
            y=list(scores.values()),
            marker_color=colors,
            text=[f"{v}/10" for v in scores.values()],
            textposition='outside',
            textfont=dict(size=13, color='#333')
        )
    ])
    fig.update_layout(
        title=dict(text='Interview Performance Breakdown', font=dict(size=16)),
        yaxis=dict(
            title='Score (out of 10)',
            range=[0, 11],
            tickmode='linear',
            tick0=0, dtick=1,
            gridcolor='#eee'
        ),
        xaxis=dict(tickfont=dict(size=13)),
        plot_bgcolor='white',
        paper_bgcolor='white',
        showlegend=False,
        height=380,
        margin=dict(t=50, l=40, r=40, b=40)
    )
    return fig


def render_evaluation(eval_data: dict):
    """Renders the evaluation section. Always call this when evaluation_done is True."""
    if not isinstance(eval_data, dict) or not eval_data:
        st.error("No evaluation data found. Please end the interview first.")
        return

    scores = {
        "Structure":    eval_data.get("structure", 0) * 2,
        "Assumptions":  eval_data.get("assumptions", 0) * 2,
        "Segmentation": eval_data.get("segmentation", 0) * 2,
        "Math":         eval_data.get("math", 0) * 2,
        "Context":      eval_data.get("context", 0) * 2,
    }
    overall = round(sum(scores.values()) / len(scores), 1)

    # Header
    st.markdown("""
    <div class="eval-header">
        <h2 style="margin:0">📊 Interview Evaluation</h2>
        <p style="margin:4px 0 0 0; opacity:0.85">Here's how you performed</p>
    </div>
    """, unsafe_allow_html=True)

    # Overall score
    overall_color = "#1a73e8" if overall >= 7 else "#f4b400" if overall >= 5 else "#ea4335"
    st.markdown(f"""
    <div class="score-overall">
        <h1 style="color:{overall_color}; margin:0; font-size:48px">{overall}/10</h1>
        <p style="color:#888; margin:4px 0 0 0">Overall Score</p>
    </div>
    """, unsafe_allow_html=True)

    # Score cards
    cols = st.columns(5)
    for i, (label, value) in enumerate(scores.items()):
        with cols[i]:
            color = "#1a73e8" if value >= 7 else "#f4b400" if value >= 5 else "#ea4335"
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color:{color}">{value}/10</h3>
                <p>{label}</p>
            </div>
            """, unsafe_allow_html=True)

    # Chart
    st.plotly_chart(create_score_chart(scores), use_container_width=True)

    # Feedback columns
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("**🔍 Filters Missed**")
        st.info(eval_data.get("filters_missed", "None noted."))
    with col_b:
        st.markdown("**✅ Key Strengths**")
        st.success(eval_data.get("key_strengths", "None noted."))
    with col_c:
        st.markdown("**📈 Areas to Improve**")
        st.warning(eval_data.get("areas_for_improvement", "None noted."))


# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────
def main():
    st.title("🤖 EstiMate | Guesstimate Interview Simulator")
    st.caption("Powered by Groq + LLaMA 3.3 70B · Free & Fast")

    # Session state init
    defaults = {
        'messages': [],
        'interview_started': False,
        'evaluation_done': False,
        'chatbot': None,
        'form_submitted': False,
        'evaluation': {},
        'auto_eval_triggered': False,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # ── SIDEBAR ──
    with st.sidebar:
        st.header("⚙️ Controls")

        try:
            api_key = st.secrets["GROQ"]["GROQ_API_KEY"]
        except Exception:
            api_key = st.text_input("Groq API Key (free at groq.com):", type="password")

        st.caption(f"Model: `{GROQ_MODEL}`")

        if st.session_state.chatbot:
            turns_used = st.session_state.chatbot.turn_count
            max_turns = st.session_state.chatbot.max_turns
            progress = turns_used / max_turns
            st.progress(progress, text=f"Turns: {turns_used}/{max_turns}")
            if progress > 0.8:
                st.warning("⚠️ Approaching turn limit. Wrap up soon.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶ Start", disabled=not api_key, use_container_width=True, type="primary"):
                st.session_state.chatbot = GuesstimateChatbot(api_key)
                st.session_state.messages = []
                st.session_state.interview_started = True
                st.session_state.evaluation_done = False
                st.session_state.form_submitted = False
                st.session_state.evaluation = {}
                st.session_state.auto_eval_triggered = False
                initial = st.session_state.chatbot.start_interview()
                st.session_state.messages.append({"role": "assistant", "content": initial})
                st.rerun()

        with col2:
            end_disabled = (
                not st.session_state.interview_started
                or st.session_state.evaluation_done
            )
            if st.button("⏹ End", disabled=end_disabled, use_container_width=True):
                with st.spinner("Evaluating your interview..."):
                    evaluation = st.session_state.chatbot.evaluate_candidate()
                    st.session_state.evaluation = evaluation
                    st.session_state.evaluation_done = True
                    save_interview(st.session_state.messages, evaluation)
                st.success("Evaluation complete! Scroll down to see your results.")
                st.rerun()

        st.divider()
        st.markdown("""
**Tips for good guesstimates:**
- Ask 2–3 clarifying questions first
- Define your scope clearly
- Segment before calculating
- State assumptions explicitly
- Sanity-check your final number
- Say **"I'm done"** when finished
""")

    # ── NOT STARTED ──
    if not st.session_state.interview_started:
        st.markdown("""
        <div style="text-align:center; padding: 60px 20px; color: #888;">
            <div style="font-size: 64px">🎯</div>
            <h3>Ready to practice?</h3>
            <p>Hit <b>Start</b> in the sidebar to begin your guesstimate interview.</p>
            <p style="font-size:13px">Free to use · Powered by Groq · No cost limit</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── PROBLEM BANNER ──
    if st.session_state.chatbot and st.session_state.chatbot.current_problem:
        st.markdown(f"""
        <div class="problem-banner">
            📊 <b>Problem:</b> {st.session_state.chatbot.current_problem}
        </div>
        """, unsafe_allow_html=True)

    # ── CHAT MESSAGES ──
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ── CHAT INPUT (only when interview active) ──
    if not st.session_state.evaluation_done:
        st.markdown("""
        <div class="tip-box">
            💡 Ask clarifying questions, then walk through your estimate. Type <b>"I'm done"</b> when finished.
        </div>
        """, unsafe_allow_html=True)

        user_input = st.chat_input("Your response...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            # ── AUTO-DETECT "I'm done" ──
            if user_signaled_done(user_input) and not st.session_state.auto_eval_triggered:
                st.session_state.auto_eval_triggered = True

                # Let interviewer acknowledge first
                with st.spinner("Interviewer responding..."):
                    ack = st.session_state.chatbot.conduct_interview(user_input)
                st.session_state.messages.append({"role": "assistant", "content": ack})
                with st.chat_message("assistant"):
                    st.write_stream(response_generator(ack))

                # Now evaluate
                with st.spinner("Evaluating your performance..."):
                    evaluation = st.session_state.chatbot.evaluate_candidate()
                    st.session_state.evaluation = evaluation
                    st.session_state.evaluation_done = True
                    save_interview(st.session_state.messages, evaluation)

                st.rerun()

            else:
                with st.spinner("Interviewer thinking..."):
                    response = st.session_state.chatbot.conduct_interview(user_input)

                if response == "TURN_LIMIT_EXCEEDED":
                    st.warning("Turn limit reached. Auto-evaluating now...")
                    with st.spinner("Evaluating..."):
                        evaluation = st.session_state.chatbot.evaluate_candidate()
                        st.session_state.evaluation = evaluation
                        st.session_state.evaluation_done = True
                        save_interview(st.session_state.messages, evaluation)
                else:
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    with st.chat_message("assistant"):
                        st.write_stream(response_generator(response))

                st.rerun()

    # ── EVALUATION SECTION ──
    if st.session_state.evaluation_done:
        st.divider()

        # ── FEEDBACK FORM (shown before results) ──
        if not st.session_state.form_submitted:
            st.subheader("📝 Quick Feedback — Unlock Your Results")
            st.caption("Fill this in to view your scores and detailed feedback.")

            with st.form(key="feedback_form"):
                c1, c2 = st.columns(2)
                with c1:
                    first_name = st.text_input("First Name *")
                    college_name = st.text_input("College *")
                    knowledge_level = st.selectbox(
                        "Your Level *",
                        ["Beginner", "Intermediate", "Advanced"],
                        index=None,
                        placeholder="Select level"
                    )
                    reuse = st.selectbox(
                        "Would you use future versions? *",
                        ["Yes", "No"],
                        index=None,
                        placeholder="Select"
                    )
                with c2:
                    last_name = st.text_input("Last Name")
                    year_of_passing = st.text_input("Year of Passing *")
                    expected_score = st.slider("Expected Score (out of 10) *", 0, 10, 5)

                session_feedback = st.text_area("How did the session go? *", placeholder="Describe your experience...")
                overall_experience = st.text_area("Overall experience with EstiMate? *", placeholder="Any suggestions for improvement?")
                st.caption("* Required fields")

                submitted = st.form_submit_button(
                    "Submit & View My Results →",
                    type="primary",
                    use_container_width=True
                )

            if submitted:
                missing = []
                if not first_name: missing.append("First Name")
                if not college_name: missing.append("College")
                if not year_of_passing: missing.append("Year of Passing")
                if not knowledge_level: missing.append("Your Level")
                if not session_feedback: missing.append("Session Feedback")
                if not overall_experience: missing.append("Overall Experience")
                if not reuse: missing.append("Would you reuse?")

                if missing:
                    st.warning(f"Please fill required fields: {', '.join(missing)}")
                else:
                    # Save to Google Sheets
                    try:
                        conn = get_connection()
                        existing_data = load_existing_data()
                        feedback_df = pd.DataFrame([{
                            "Submission Time":    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            "first_name":         first_name,
                            "last_name":          last_name,
                            "college_name":       college_name,
                            "year_of_passing":    year_of_passing,
                            "knowledge_level":    knowledge_level,
                            "session_feedback":   session_feedback,
                            "expected_score":     expected_score,
                            "overall_experience": overall_experience,
                            "reuse":              reuse,
                        }])
                        updated_df = pd.concat([existing_data, feedback_df], ignore_index=True)
                        conn.update(worksheet="data", data=updated_df)
                        st.success("✅ Feedback saved!")
                    except Exception as e:
                        st.warning(f"Could not save to Google Sheets: {e}")

                    st.session_state.form_submitted = True
                    st.rerun()

        # ── SHOW RESULTS (after form submitted) ──
        if st.session_state.form_submitted:
            render_evaluation(st.session_state.evaluation)

            # ── PDF DOWNLOAD ──
            st.divider()
            col_dl1, col_dl2 = st.columns([1, 1])
            with col_dl1:
                if st.button("📄 Generate PDF Transcript", use_container_width=True):
                    with st.spinner("Generating PDF..."):
                        file_name = download_interview_transcript(
                            st.session_state.messages,
                            st.session_state.evaluation
                        )
                    with open(file_name, "rb") as f:
                        st.download_button(
                            label="⬇️ Download PDF",
                            data=f.read(),
                            file_name=file_name,
                            mime="application/pdf",
                            use_container_width=True
                        )
            with col_dl2:
                if st.button("🔄 Start New Interview", use_container_width=True, type="primary"):
                    for key in ['messages', 'interview_started', 'evaluation_done',
                                'chatbot', 'form_submitted', 'evaluation', 'auto_eval_triggered']:
                        st.session_state[key] = ([] if key == 'messages'
                                                  else {} if key == 'evaluation'
                                                  else None if key == 'chatbot'
                                                  else False)
                    st.rerun()


if __name__ == "__main__":
    main()
