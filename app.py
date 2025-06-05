from flask import Flask, request, jsonify, send_file
import pdfx 
import re
import json
from groq import Groq
import os
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = tempfile.mkdtemp()
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize Groq client
client = Groq(api_key="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")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



def extract_resume_data(pdf_path):
    """Extract text and process with Groq"""
    def read_pdf_file(pdf_path):
        pdf = pdfx.PDFx(pdf_path)
        text = pdf.get_text()
        urls = pdf.get_references_as_dict().get("url", [])
        return text + "\n\nExtracted URLs:\n" + "\n".join(urls)

    resume_text = read_pdf_file(pdf_path)

    # Clean resume text to reduce token usage
    resume_text = re.sub(r'\s+', ' ', resume_text)  # Replace multiple whitespace with single space
    resume_text = re.sub(r'[^\x00-\x7F]+', ' ', resume_text)  # Remove non-ASCII characters
    resume_text = resume_text.strip()

    prompt = f"""
You are a professional resume parser. Extract the following fields from the resume below and respond ONLY in the exact JSON format shown, without adding or removing any keys.
Instructions:
- ONLY extract data if it is explicitly stated in the resume. DO NOT infer, guess, or fill in missing data
- Follow formatting rules exactly for each field.
Expected JSON structure:
{{
    "name": "First Last",  // Only first and second name.
    "location": "Governorate Country", //e.g.: Cairo Egypt - Madrid spain
    "email": "example@example.com",  // Must be lowercase.
    "education": ["Degree, Institution, Year"] all in one line Example Bachelor Degree in Computer Science, Helwan University, 2021 - 2025 GPA 3.2,
    "skills": ["Only", "Technical", "Skills", "10 Maxiumum"],  // No soft skills. Only technologies, tools, languages, or platforms.
    "career_name": "Predict the MOST SPECIFIC job title based strictly on the resume’s technical skills, tools, and projects — do not guess or generalize, The format must be: '[Technology/Tool] [Role] [Optional Specialization or Industry]'
Return concise but complete titles. DO NOT return vague outputs like 'Frontend Developer', 'Mobile Developer', or 'Software Engineer'. Always include the tech stack or tool when mentioned.
Examples:
- 'React Frontend Developer'
- 'Flutter Mobile App Developer'
    "projects": ["Project 1", "Project 2"],
    "github_username": "username",  // Only return if found inside an explicit GitHub URL. Otherwise, return null.
    "linkedin_url": "https://linkedin.com/in/username"  //  Only return if found inside an explicit linkedin URL. Otherwise, return null.
}}

Resume Text (truncated):
{resume_text}
"""

    
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}

@app.route('/process-resume', methods=['POST'])
def process_resume():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are allowed"}), 400

    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(pdf_path)

        # Process PDF
        
        parsed_data = extract_resume_data(pdf_path)


        response = {
            "data": parsed_data
        }
        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    



if __name__ == '__main__':

    app.run(host='0.0.0.0', port=8080)


'''
    "Weaknesses_in_Resume": "Can't be null, Generate 2–4 full sentences that clearly mention 3–5 weaknesses visible in the resume. Only include specific and fixable issues that are obvious in the text, such as missing contact details, unclear project descriptions, outdated skills, or lack of metrics. Avoid assumptions.",
    "Technical_Career_Tips": "Can't be null, Generate 2–4 concise and practical sentences giving 3–5 technical suggestions based strictly on the skills already listed. Mention adjacent tools or languages to learn, certifications to consider, or improvements to current projects or tech stack. No general advice or guessing.",
    "resume_score": 0,  // Return a whole number from 0 to 100 based ONLY on the following strict rules. Do not guess or add partial credit. Do not include any explanations.
'''
