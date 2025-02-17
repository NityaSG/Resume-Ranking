import os
import json
import tempfile
from io import BytesIO
import dotenv
from openai import OpenAI
dotenv.load_dotenv()
client = OpenAI()

import PyPDF2
import docx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Job Ranking Criteria Extraction API",
    description="Upload a job description (PDF or DOCX) to extract ranking criteria such as skills, certifications, experience, and qualifications.",
    version="1.0.0"
)

def extract_text_from_pdf(file_stream: BytesIO) -> str:
    """Extract text from a PDF file using PyPDF2."""
    try:
        reader = PyPDF2.PdfReader(file_stream)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading PDF file: {e}")

def extract_text_from_docx(file_stream: BytesIO) -> str:
    """Extract text from a DOCX file using python-docx."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(file_stream.read())
            tmp_path = tmp.name

        doc = docx.Document(tmp_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        os.unlink(tmp_path)
        return text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading DOCX file: {e}")

def extract_criteria_from_text(job_text: str) -> dict:
    """
    Uses the latest OpenAI SDK chat API to extract key ranking criteria from the job description text.
    The assistant returns a JSON object with three keys: 'Must have', 'Good to have', and 'Nice to have'.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are an HR expert that extracts key ranking criteria from job descriptions. "
                "Extract key features from the job description and structure them into a JSON object with three keys: 'Must have', 'Good to have', and 'Nice to have'. "
                "Each of these keys should map to a nested JSON object where the keys represent the criteria (e.g., years of experience, certifications, skills) "
                "and the values can be booleans, strings, numbers, etc. "
                "Do not include any extra text, explanations, or markdown formatting—output only a valid JSON object. "
                "Example output:\n"
                "{\n"
                "  \"Must have\": {\n"
                "    \"experience in python in years\": \"2\",\n"
                "    \"experience in machine learning in years\": \"1\",\n"
                "    \"postgraduate degree\": true,\n"
                "    \"Cloud skills\": \"AWS, Azure with projects done in such fields\",\n"
                "    \"Gen AI related project experience\": \"Candidate should have worked on at least 2 projects using RAG and GPT models\"\n"
                "  },\n"
                "  \"Good to have\": {\n"
                "    ...\n"
                "  },\n"
                "  \"Nice to have\": {\n"
                "    ...\n"
                "  }\n"
                "}"
            )
        },
        {
            "role": "user",
            "content": f"Job Description:\n{job_text}"
        }
    ]
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=300,
            temperature=0.2
        )
        criteria_text = response.choices[0].message.content.strip()

        # Normalize the response by replacing Python booleans with JSON booleans.
        normalized_text = criteria_text.replace("True", "true").replace("False", "false")

        try:
            parsed = json.loads(normalized_text)
            return parsed
        except Exception:
            # Fallback: use ast.literal_eval if json.loads fails.
            import ast
            parsed = ast.literal_eval(criteria_text)
            return parsed
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing text with OpenAI: {e}")

@app.post(
    "/extract-criteria",
    summary="Extract Ranking Criteria",
    description="Upload a job description file (PDF or DOCX) to extract ranking criteria such as skills, certifications, experience, and qualifications."
)
async def extract_criteria(file: UploadFile = File(...)):
    # Validate file type based on MIME type or file extension
    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF and DOCX are supported.")

    try:
        contents = await file.read()
        file_stream = BytesIO(contents)

        if file.filename.lower().endswith(".pdf"):
            job_text = extract_text_from_pdf(file_stream)
        elif file.filename.lower().endswith(".docx"):
            file_stream.seek(0)
            job_text = extract_text_from_docx(file_stream)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file extension. Only PDF and DOCX are supported.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading the file: {e}")

    if not job_text.strip():
        raise HTTPException(status_code=400, detail="The uploaded file is empty or text could not be extracted.")

    criteria = extract_criteria_from_text(job_text)
    return JSONResponse(content={"criteria": criteria})


