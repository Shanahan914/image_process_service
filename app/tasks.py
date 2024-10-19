import uuid


# generate unique filename for uploaded inages
def generate_unique_filename(filename: str) -> str:
    unique_id = str(uuid.uuid4())  # Generates a unique identifier
    file_extension = filename.split('.')[-1]  # Preserves the file extension
    return f"{unique_id}.{file_extension}"

