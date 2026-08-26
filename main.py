from dotenv import load_dotenv
load_dotenv()  # must run BEFORE importing storage/database

import hashlib
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException

import storage
from database import documents_collection

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Land Record API is running"}


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    contents = await file.read()
    file_hash = hashlib.sha256(contents).hexdigest()

    # Check if this exact file already exists
    existing = documents_collection.find_one({"file_hash": file_hash})
    if existing:
        return {
            "message": "This file has already been uploaded",
            "duplicate": True,
            "document_id": str(existing["_id"]),
            "filename": existing["filename"],
            "file_url": existing["file_url"]
        }

    # New file — upload to storage
    try:
        file_url = storage.upload_file(contents, file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {str(e)}")

    # Save record to MongoDB
    document = {
        "filename": file.filename,
        "file_hash": file_hash,
        "file_url": file_url,
        "content_type": file.content_type,
        "size_bytes": len(contents),
        "status": "uploaded",
        "uploaded_at": datetime.utcnow()
    }
    result = documents_collection.insert_one(document)

    return {
        "message": "File uploaded successfully",
        "duplicate": False,
        "document_id": str(result.inserted_id),
        "filename": file.filename,
        "file_url": file_url
    }