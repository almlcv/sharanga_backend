# config/dojo_config.py

# ------------------- Base Video & OJT Data -------------------
CRT_VIDEOS = [
    {"title": "About Safety", "link": "https://youtu.be/6xIOtUPu0Ug", "type": "CRT"},
    {"title": "About 1S, 2S", "link": "https://youtu.be/6xIOtUPu0Ug", "type": "CRT"},
    {"title": "About Tag Awareness", "link": "https://youtu.be/Kf7gKWYC5mI", "type": "CRT"},
    {"title": "About Product Knowledge", "link": "https://youtu.be/Kf7gKWYC5mI", "type": "CRT"},
]

OJT_TASKS = [
    {"title": "About Material Handling", "type": "OJT", "completed": False},
    {"title": "About Process Knowledge", "type": "OJT", "completed": False} ]

DEFAULT_FLAGS = {
    "completed": False,
    "completed_at": None }



# ------------------- HORIZONTAL INJECTION MOLDING -------------------
LEVEL_1_HORIZONTAL_INJECTION_MOLDING = {
    "videos": CRT_VIDEOS,
    "ojt_tasks": OJT_TASKS,
    
}

# ------------------- FINAL INSPECTION / PACKAGING -------------------
LEVEL_1_FINAL_INSPECTION_PACKAGING = {
    "videos": CRT_VIDEOS,
    "ojt_tasks": OJT_TASKS,
   
}



LEVEL_1_FORM_UPLOADED = {
    "form_uploaded": False,
    "completed": False,
    "completed_at": None 
}

