# Resume Ranking Project

loom rec link : https://www.loom.com/share/8b7dd359306d41e78e6ac91701495fb0?sid=9a4d53e5-0835-471f-92ec-f4e9b99d1df4

This project consists of two FastAPI applications that work together to automate candidate evaluation using GPT-4:

1. **Job Ranking Criteria Extraction API (`extract.py`)**  
   Extracts key ranking criteria (e.g., skills, certifications, experience) from a job description file (PDF or DOCX) using GPT-4.

2. **Resume Scoring API (`rank.py`)**  
   Scores candidate resumes against the provided ranking criteria by leveraging GPT-4 and outputs a CSV report with detailed scores.

---

## Code Explanations

### `extract.py` – Job Ranking Criteria Extraction API

- **Purpose:**  
  This API accepts a job description file upload (PDF or DOCX), extracts its text, and uses GPT-4 to derive structured ranking criteria.

- **Key Components:**
  - **File Extraction:**  
    Uses [PyPDF2](https://pypi.org/project/PyPDF2/) for PDFs and [python-docx](https://pypi.org/project/python-docx/) for DOCX files to extract raw text.
  - **Criteria Extraction:**  
    Constructs a prompt for GPT-4 that instructs it to extract and structure the criteria into a JSON object with three keys: `"Must have"`, `"Good to have"`, and `"Nice to have"`.
  - **Endpoint:**  
    - **Route:** `/extract-criteria`  
    - **Method:** `POST`  
    - **Input:** A job description file (PDF or DOCX).  
    - **Output:** A JSON object with extracted ranking criteria.

- **Sample Payload (Request):**  
  **Note:** Since this endpoint accepts a file upload, the payload is a job description document. For example, a job description file might include:
  > **Job Description Text (inside a PDF or DOCX):**  
  > "We are looking for a candidate with at least 3 years of experience in Python and 2 years in machine learning. A bachelor's degree is required, and cloud experience (AWS or Azure) is a plus."

- **Sample Response:**  

  ```json
  {
    "criteria": {
      "Must have": {
        "experience in python in years": "3",
        "experience in machine learning in years": "2",
        "bachelor's degree": true
      },
      "Good to have": {
        "Cloud skills": "AWS, Azure"
      },
      "Nice to have": {
        "experience in openai projects": true
      }
    }
  }
  ```

---

### `rank.py` – Resume Scoring API

- **Purpose:**  
  This API accepts a JSON string containing nested ranking criteria along with a list of resume files. It uses GPT-4 to evaluate and score each resume based on the criteria.

- **Key Components:**
  - **File Extraction:**  
    Similar to `extract.py`, it extracts resume text from PDFs (via PyPDF2) or DOCX files (via python-docx).
  - **Scoring with GPT-4:**  
    Constructs a prompt that includes:
    - Candidate name (derived from the filename).
    - The full resume text.
    - The nested criteria in JSON format.
    
    GPT-4 is then instructed to evaluate each criterion with a continuous scoring range:
    - **Must have:** Score from 0 to 10.
    - **Good to have:** Score from 0 to 5.
    - **Nice to have:** Score from 0 to 2.
    
    It also computes a total score as the sum of all individual scores.
  - **Output Generation:**  
    The results for each resume are written to a CSV file, with columns for candidate name, individual criterion scores, and the total score.
  - **Endpoint:**  
    - **Route:** `/score-resumes`  
    - **Method:** `POST`  
    - **Inputs:**  
      - `criteria`: A JSON string representing nested ranking criteria.
      - `files`: One or more resume files (PDF or DOCX).
    - **Output:** A downloadable CSV file containing the evaluation results.

- **Sample Payload (Request):**  

  **Criteria JSON (as a form field):**

  ```json
  {
    "criteria": {
      "Must have": {
        "experience in python": true,
        "experience in machine learning": true
      },
      "Good to have": {
        "cloud certification": true
      },
      "Nice to have": {
        "experience with openai": true
      }
    }
  }
  ```

  **Resume File:**  
  A resume file named `John Doe.pdf` that contains the candidate’s resume text.

- **Sample CSV Output (Response):**

  ```csv
  Candidate Name,Must have: experience in python,Must have: experience in machine learning,Good to have: cloud certification,Nice to have: experience with openai,Total Score
  John Doe,8,7,4,2,21
  ```

  In this example, the GPT evaluation determined:
  - **Must have:**  
    - "experience in python": 8  
    - "experience in machine learning": 7  
  - **Good to have:**  
    - "cloud certification": 4  
  - **Nice to have:**  
    - "experience with openai": 2  
  - **Total Score:** Sum of the above scores (8 + 7 + 4 + 2 = 21)
