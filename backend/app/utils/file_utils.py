import os
import uuid
from fastapi import UploadFile

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'uploads')
UPLOAD_DIR = os.path.abspath(UPLOAD_DIR)

os.makedirs(UPLOAD_DIR, exist_ok=True)

def save_upload_file(upload_file: UploadFile) -> str:
    if not upload_file.filename.endswith('.csv'):
        raise ValueError('Only CSV files are allowed.')
    unique_filename = f"{uuid.uuid4()}_{upload_file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    with open(file_path, 'wb') as out_file:
        content = upload_file.file.read()
        out_file.write(content)
    return file_path 