import os
import pandas as pd
from PyPDF2 import PdfReader
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import re
import io
import docx2txt

# Load environment variables from a .env file
load_dotenv()

# Configure generative AI model with the Google API key
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Model configuration for text generation
generation_config = {
    "temperature": 0.4,
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 4096,
}

# Define safety settings for content generation
safety_settings = [
    {"category": f"HARM_CATEGORY_{category}", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
    for category in ["HARASSMENT", "HATE_SPEECH", "SEXUALLY_EXPLICIT", "DANGEROUS_CONTENT"]
]

def extract_text_from_docx(file):
    try:
        text = docx2txt.process(file)
        return text
    except Exception as e:
        st.error(f"Error extracting text from DOCX file: {e}")
        return ""

def extract_text_from_pdf(file):
    try:
        text = ""
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error extracting text from PDF file: {e}")
        return ""

def extract_text_from_file(file):
    try:
        content_type = file.type
        content = file.read()

        if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return extract_text_from_docx(io.BytesIO(content))
        elif content_type == "application/pdf":
            return extract_text_from_pdf(io.BytesIO(content))
        else:
            st.warning("Unsupported file format. Please upload .docx or .pdf files.")
            return ""
    except Exception as e:
        st.error(f"Error extracting text from file: {e}")
        return ""

def generate_response_from_gemini(input_text, prompt):
    try:
        llm = genai.GenerativeModel(
            model_name="gemini-pro",
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
        output = llm.generate_content(f"{prompt}\n\n{input_text}")
        return output.text
    except Exception as e:
        st.error(f"Error generating response from Gemini: {e}")
        return ""

def normalize_text(text):
    return re.sub(r'\s+', '', text.lower())

def evaluate_resume(resume_text, required_skills, optional_skills):
    try:
        normalized_resume_text = normalize_text(resume_text)

        def create_patterns(skill):
            normalized_skill = normalize_text(skill)
            patterns = [
                normalized_skill,
                re.escape(skill.lower().replace(' ', '')),  # Handle potential spaces between words
            ]
            return patterns

        def match_skills(skills, text):
            found_skills = {skill: False for skill in skills}
            for skill in skills:
                patterns = create_patterns(skill)
                for pattern in patterns:
                    if re.search(pattern, text):
                        found_skills[skill] = True
                        break
            return found_skills

        required_skills_list = required_skills.lower().split('\n')
        optional_skills_list = optional_skills.lower().split('\n')

        required_skills_found = match_skills(required_skills_list, normalized_resume_text)
        optional_skills_found = match_skills(optional_skills_list, normalized_resume_text)

        required_match_percentage = sum(required_skills_found.values()) / len(required_skills_found) * 100
        optional_match_percentage = sum(optional_skills_found.values()) / len(optional_skills_found) * 100

        return required_skills_found, optional_skills_found, required_match_percentage, optional_match_percentage
    except Exception as e:
        st.error(f"Error evaluating resume: {e}")
        return {}, {}, 0.0, 0.0

st.title('Resume Screening')

# Columns for required and optional skills
col1, col2 = st.columns(2)

with col1:
    required_skills = st.text_area("Enter Required Skills (one skill per line):", height=200)
with col2:
    optional_skills = st.text_area("Enter Optional Skills (one skill per line):", height=200)

uploaded_files = st.file_uploader("Upload multiple resumes (.docx, .pdf)", accept_multiple_files=True)

if st.button("Analyze Resumes"):
    if uploaded_files and required_skills and optional_skills:
        results = []
        for uploaded_file in uploaded_files:
            resume_text = extract_text_from_file(uploaded_file)
            if resume_text:
                required_skills_found, optional_skills_found, required_match_percentage, optional_match_percentage = evaluate_resume(resume_text, required_skills, optional_skills)

                experience_summary = generate_response_from_gemini(resume_text, "Extract the experience summary from the following resume:")
                education_summary = generate_response_from_gemini(resume_text, "Extract the education summary from the following resume:")

                results.append({
                    "Resume name": uploaded_file.name,
                    "Required Skills": ", ".join([skill for skill, found in required_skills_found.items() if found]),
                    "Optional Skills": ", ".join([skill for skill, found in optional_skills_found.items() if found]),
                    "Required skills % match": f"{required_match_percentage:.2f}%",
                    "Optional skills % match": f"{optional_match_percentage:.2f}%",
                    "Experience Summary": experience_summary,
                    "Education Summary": education_summary,
                })
        
        if results:
            results_df = pd.DataFrame(results)
            st.dataframe(results_df)
    else:
        st.warning("Please upload resumes, enter required skills, and optional skills")
