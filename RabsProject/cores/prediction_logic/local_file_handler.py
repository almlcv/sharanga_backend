import os
from shutil import copyfileobj

def create_user_dir(user_email):
    user_dir = os.path.join("classification/uploads", user_email)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def generate_timestamped_filename(filename, file_id, timestamp):
    name, ext = os.path.splitext(filename)
    return f"{timestamp}_{file_id}{ext}"

def save_upload_file(upload_file, destination_path):
    with open(destination_path, "wb") as buffer:
        copyfileobj(upload_file.file, buffer)


