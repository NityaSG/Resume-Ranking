import io
import csv
import json
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse
from openai import OpenAI  # Latest OpenAI client integration
import PyPDF2
import docx
import dotenv
dotenv.load_dotenv()
# Initialize the OpenAI client (ensure your OPENAI_API_KEY is set in your environment)
client = OpenAI()

app = FastAPI(
    title="GPT Integrated Resume Scoring API with Continuous Scoring",
    description="Score resumes using GPT (gpt-4o) based on nested criteria with continuous scoring ranges.",
    version="1.0"
)

def extract_text_from_pdf(uploaded_file: UploadFile) -> str:
    """Extract text from a PDF file using PyPDF2."""
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file.file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing PDF: {e}")
    finally:
        uploaded_file.file.seek(0)
    return text

def extract_text_from_docx(uploaded_file: UploadFile) -> str:
    """Extract text from a DOCX file using python-docx."""
    try:
        document = docx.Document(uploaded_file.file)
        text = "\n".join(para.text for para in document.paragraphs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing DOCX: {e}")
    finally:
        uploaded_file.file.seek(0)
    return text

def get_gpt_scores(candidate_name: str, resume_text: str, criteria_data: dict) -> dict:
    """
    Call GPT (using the latest gpt-4o integration) to score the candidate's resume.
    
    The prompt provides:
      - Candidate Name
      - Full Resume Text
      - Nested Criteria (JSON)
      - Scoring instructions:
          For each criterion in **Must have**:
            - Evaluate the candidate's resume and assign a score between 0 and 10.
              (0 means not met at all, 10 means fully met, and intermediate values are allowed.)
          For each criterion in **Good to have**:
            - Assign a score between 0 and 5.
          For each criterion in **Nice to have**:
            - Assign a score between 0 and 2.
            
    GPT should return a JSON object in the following exact format:
    
    {
      "candidate_name": "Candidate Name",
      "scores": {
          "Must have": {
              "criterion 1": score,
              "criterion 2": score,
              ...
          },
          "Good to have": { ... },
          "Nice to have": { ... }
      },
      "total_score": total_score
    }
    """
    system_message = {
        "role": "system",
        "content": "You are an expert resume evaluator. Score candidates based on provided criteria using continuous scoring ranges."
    }
    user_message = {
        "role": "user",
        "content": (
            f"Candidate Name: {candidate_name}\n\n"
            f"Resume Text:\n{resume_text}\n\n"
            "Criteria (nested JSON):\n"
            f"{json.dumps(criteria_data, indent=2)}\n\n"
            "Instructions:\n"
            "For each criterion in the nested groups, evaluate the candidate's resume and assign scores as follows:\n\n"
            "1. **Must have**: Assign a score between 0 and 10. Use 0 if the criterion is not met at all, 10 if fully met, "
            "and any intermediate value (e.g., 7) if the evidence is partial.\n\n"
            "2. **Good to have**: Assign a score between 0 and 5, where 0 means not met and 5 means strongly met. "
            "Intermediate values are allowed.\n\n"
            "3. **Nice to have**: Assign a score between 0 and 2, where 0 means not met and 2 means strongly met, "
            "with intermediate scores allowed.\n\n"
            "After evaluating all criteria, compute the total score as the sum of all individual scores. "
            "Return a JSON object in the following format exactly:\n\n"
            "{\n"
            '  "candidate_name": "Candidate Name",\n'
            '  "scores": {\n'
            '      "Must have": {\n'
            '          "criterion 1": score,\n'
            '          "criterion 2": score,\n'
            '          ...\n'
            '      },\n'
            '      "Good to have": { ... },\n'
            '      "Nice to have": { ... }\n'
            '  },\n'
            '  "total_score": total_score\n'
            "}\n\n"
            "Ensure that the JSON is properly formatted."
        )
    }
    messages = [system_message, user_message]
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling GPT API: {e}")
    
    reply = completion.choices[0].message.content[7:-3]
    try:
        result = json.loads(reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing GPT response: {e}. Response was: {reply}")
    return result

@app.post("/score-resumes", summary="Score Resumes Using GPT with Continuous Scoring")
async def score_resumes(
    criteria: str = Form(
        ...,
        description=(
            "A JSON string representing nested criteria groups. Example format:\n"
            '{ "criteria": { "Must have": { "experience in AI application development": true, ... }, ... } }'
        )
    ),
    files: list[UploadFile] = File(
        ...,
        description="List of resume files (PDF or DOCX)."
    )
):
    """
    Accepts nested ranking criteria and resume files, then uses the latest GPT integration (gpt-4o)
    to score each resume based on the criteria using the following continuous scoring ranges:
    
    - **Must have:** 0 to 10 (with intermediate values allowed).
    - **Good to have:** 0 to 5 (with intermediate values allowed).
    - **Nice to have:** 0 to 2 (with intermediate values allowed).
    
    Returns a CSV file containing each candidate's name, individual criterion scores, and total score.
    """
    try:
        criteria_payload = json.loads(criteria)
        criteria_data = criteria_payload.get("criteria")
        if not isinstance(criteria_data, dict):
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid criteria format. Must be a JSON with a 'criteria' key containing nested groups.")
    
    # Flatten the criteria for the CSV header.
    flattened_criteria = []
    headers = []
    for group, group_criteria in criteria_data.items():
        if not isinstance(group_criteria, dict):
            continue
        for crit_key in group_criteria.keys():
            flattened_criteria.append((group, crit_key))
            headers.append(f"{group}: {crit_key}")
    
    output = io.StringIO()
    writer = csv.writer(output)
    csv_header = ["Candidate Name"] + headers + ["Total Score"]
    writer.writerow(csv_header)
    
    # Process each resume file.
    for uploaded_file in files:
        filename = uploaded_file.filename
        candidate_name = filename.rsplit(".", 1)[0]
        if filename.lower().endswith(".pdf"):
            resume_text = extract_text_from_pdf(uploaded_file)
        elif filename.lower().endswith(".docx"):
            resume_text = extract_text_from_docx(uploaded_file)
        else:
            # Skip unsupported file types.
            continue
        
        # Call GPT to score this candidate.
        gpt_result = get_gpt_scores(candidate_name, resume_text, criteria_data)
        
        # Prepare a row in the CSV.
        row = [candidate_name]
        for group, crit_key in flattened_criteria:
            group_scores = gpt_result.get("scores", {}).get(group, {})
            score = group_scores.get(crit_key, 0)
            row.append(score)
        row.append(gpt_result.get("total_score", 0))
        writer.writerow(row)
    
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=scores.csv"
    return response

# To run the application:
# uvicorn your_filename:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
