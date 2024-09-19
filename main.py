from flask import Flask, request, jsonify
import io
import docx
import fitz
import re
from datetime import datetime
from pymongo import MongoClient
import gridfs
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
# MongoDB configuration
client = MongoClient("mongodb+srv://yash_bunker:Bunkers@cluster0.h45uu.mongodb.net/resume?retryWrites=true&w=majority&appName=Cluster0")
db = client['resume']
fs = gridfs.GridFS(db)

# Function to analyze resume
def analyze_resume(file_id):
    file_data = fs.get(file_id).read()
    if file_data.startswith(b'%PDF'):
        return analyze_pdf(file_data)
    elif file_data.startswith(b'PK'):
        return analyze_docx(file_data)
    return 0

def analyze_docx(file_data):
    document = docx.Document(io.BytesIO(file_data))
    text = "\n".join([para.text for para in document.paragraphs])
    score = calculate_score(text)
    return score

def analyze_pdf(file_data):
    doc = fitz.open(stream=file_data, filetype='pdf')
    text = ""
    for page in doc:
        text += page.get_text()
    score = calculate_score(text)
    return score

def calculate_score(text):
    score = 0
    max_score = 100
    feedback = []

    # Length Check (optimal: 300-600 words)
    word_count = len(text.split())
    if 300 <= word_count <= 600:
        score += 15
    elif word_count > 600:
        score += 10
        feedback.append("The resume is too long. Consider shortening it.")
    else:
        score += 5
        feedback.append("The resume is too short. Consider adding more relevant details.")

    # Key Sections
    sections = {
        "Contact Information": r"(phone|email|contact)",
        "Education": r"(education|university|degree)",
        "Work Experience": r"(experience|work history|employment)",
        "Skills": r"(skills|abilities|competencies)",
        "Achievements/Certifications": r"(certifications|awards|achievements)"
    }

    for section, pattern in sections.items():
        if re.search(pattern, text, re.IGNORECASE):
            score += 10
        else:
            feedback.append(f"Missing key section: {section}. Please include this.")

    # Readability Check
    if text.count("•") > 5:  # Bullet points
        score += 10
    else:
        feedback.append("Consider using bullet points for better readability.")

    if text.count("\n\n") > 3:  # Paragraphs
        score += 5
    else:
        feedback.append("Use more paragraph breaks for better structure.")

    # Coding Platforms
    github_pattern = re.compile(r"github", re.IGNORECASE)
    other_platforms_pattern = re.compile(r"(gitlab|bitbucket|codeforces|hackerrank|leetcode)", re.IGNORECASE)

    if github_pattern.search(text):
        score += 5
        if other_platforms_pattern.search(text):
            score += 5
    elif other_platforms_pattern.search(text):
        score += 5
        feedback.append("Consider including a GitHub link to showcase your code.")
    else:
        feedback.append("Consider adding coding platform profiles (GitHub, Codeforces, etc.).")

    # Professionalism
    informal_words_pattern = re.compile(r"(hey|hi|hello|gonna|wanna)", re.IGNORECASE)
    if not informal_words_pattern.search(text):
        score += 10
    else:
        feedback.append("Remove informal language (e.g., 'hey', 'gonna') for a more professional tone.")

    # Organization
    if text.count('\n') > 10 and re.search(r"\b\w+\b", text):
        score += 10
    else:
        feedback.append("Improve the overall organization. Ensure there are enough sections and clear headings.")

    # Years of Experience and Passing Year
    current_year = datetime.now().year
    experience_years = 0
    passing_year = None

    # Find the education section
    education_section = re.search(r"(?i)education.*?(?=\n\n|\Z)", text, re.DOTALL)
    if education_section:
        education_text = education_section.group(0)

        # Extract years from the education section
        year_pattern = re.compile(r"\b(19|20)\d{2}\b")
        years = year_pattern.findall(education_text)

        if years:
            passing_year = max(map(int, years))
            experience_years = current_year - passing_year
        else:
            feedback.append("Could not find a clear passing year. Make sure to include this information.")

    return min(score, max_score), experience_years, passing_year, feedback

# Store file in MongoDB using GridFS
def upload_to_mongo(file):
    file_id = fs.put(file, filename=file.filename)
    return file_id

@app.route('/resume', methods=['POST'])
def upload_file():
    print("Files received:", request.files.keys())  # Print the keys to verify

    # Check if 'File' is in the request.files
    if 'File' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['File']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    print("File received:", file)
    
    if file and (file.filename.endswith('.docx') or file.filename.endswith('.pdf')):
        # Upload file to MongoDB
        file_id = upload_to_mongo(file)

        # Analyze the resume
        score, experience_years, passing_year, feedback = analyze_resume(file_id)

        return jsonify({
            "score": score,
            "experience_years": experience_years,
            "passing_year": passing_year,
            "feedback": feedback,
            "file_id": str(file_id)
        }), 200

    return jsonify({"error": "Invalid file format"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6000, debug=True)
