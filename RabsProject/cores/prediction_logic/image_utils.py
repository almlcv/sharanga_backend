import cv2
import os
import uuid
import numpy as np
import os
import uuid
from datetime import datetime
from PIL import Image, ImageDraw
import os
import uuid
from zoneinfo import ZoneInfo
from datetime import datetime
from PIL import Image, ImageDraw
from datetime import datetime
from RabsProject.cores.prediction_logic.local_file_handler import create_user_dir
from RabsProject.cores.prediction_logic.local_file_handler import generate_timestamped_filename, save_upload_file
ist = datetime.now(ZoneInfo("Asia/Kolkata"))




def run_detection(model, image, conf_thresh=0.75, iou_thresh=0.75):
    results = model(image, conf=conf_thresh, iou=iou_thresh, verbose=False)
    if results and results[0].boxes:
        return results[0].boxes.xyxy.cpu().numpy()
    return []

def run_classification(model, roi):
    results = model(roi, verbose=False)
    if results and results[0].probs:
        probs = results[0].probs
        top_class = probs.top1
        class_name = model.names[top_class]
        confidence = probs.data[top_class].item()
        return class_name, confidence
    return None, None

def create_user_dir(path: str):
    os.makedirs(path, exist_ok=True)
    return path




def process_image(uploaded_file, user_email, detect_model, classify_model, expected_type, category):
    # Setup identifiers
    file_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

    base_path = os.path.join("classification", "uploads", category, user_email)
    create_user_dir(base_path)

    # File paths
    original_filename = f"{timestamp}_{file_id}.jpg"
    original_path = os.path.join(base_path, original_filename)

    # Save uploaded image
    with open(original_path, "wb") as f:
        f.write(uploaded_file.file.read())

    # Run detection model
    detect_results = detect_model(original_path, iou=0.1, agnostic_nms=True)[0]
    boxes = detect_results.boxes
    image = Image.open(original_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    incorrect_count = 0
    total_count = 0

    for box in boxes:
        xyxy = box.xyxy[0].tolist()
        x1, y1, x2, y2 = map(int, xyxy)

        # Crop object
        cropped = image.crop((x1, y1, x2, y2))
        cropped_path = os.path.join(base_path, f"crop_{uuid.uuid4()}.jpg")
        cropped.save(cropped_path)

        # Classify
        cls_result = classify_model(cropped_path, agnostic_nms=True)[0]
        if len(cls_result.names) > 0:
            predicted_class = cls_result.names[int(cls_result.probs.top1)]
        else:
            predicted_class = "unknown"

        total_count += 1

        if predicted_class.upper() != expected_type.upper():
            incorrect_count += 1
            draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
            draw.text((x1, y1), f"{predicted_class}", fill="red")
        else:
            draw.rectangle([x1, y1, x2, y2], outline="yellow", width=2)
            draw.text((x1, y1), f"{predicted_class}", fill="yellow")

        # Delete cropped file
        os.remove(cropped_path)

    # Save final processed image
    processed_filename = f"processed_{original_filename}"
    processed_path = os.path.join(base_path, processed_filename)
    image.save(processed_path)

    return {
        "file_id": file_id,
        "original_filename": original_filename,
        "processed_filename": processed_filename,
        "original_path": original_path,
        "processed_path": processed_path,
        "timestamp": timestamp,
        "incorrect_count": incorrect_count,
        "total_count": total_count
    }

















# def annotate_image(image, boxes, classify_model, expected_type):
#     mismatched_count = 0
#     total_detected = len(boxes)

#     for box in boxes:
#         x1, y1, x2, y2 = map(int, box[:4])
#         roi = image[y1:y2, x1:x2]
#         class_name, _ = run_classification(classify_model, roi)

#         if class_name:
#             is_mismatch = (class_name != expected_type)
#             if is_mismatch:
#                 mismatched_count += 1

#             label = f"{class_name}"
#             box_color = (0, 255, 0) if not is_mismatch else (0, 0, 255)  # Green if correct, red if mismatch

#             # Draw box and label
#             cv2.rectangle(image, (x1, y1), (x2, y2), box_color, thickness=1)
#             (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 1)
#             cv2.rectangle(image, (x1, y1 - th - 10), (x1 + tw + 10, y1), box_color, -1)
#             cv2.putText(image, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)

#     has_mismatch = mismatched_count > 0 or total_detected != 40
#     return image, has_mismatch, total_detected, mismatched_count


# def process_image(uploaded_file, user_email, detect_model, classify_model, expected_type):
#     # Setup paths
#     file_id = str(uuid.uuid4())
#     timestamp = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
#     user_dir = create_user_dir(user_email)

#     original_filename = f"{timestamp}_{file_id}.jpg"
#     original_path = os.path.join(user_dir, original_filename)

#     # Save the uploaded image
#     with open(original_path, "wb") as f:
#         f.write(uploaded_file.file.read())

#     # Run detection model
#     detect_results = detect_model(original_path)[0]
#     boxes = detect_results.boxes
#     image = Image.open(original_path).convert("RGB")
#     draw = ImageDraw.Draw(image)

#     incorrect_count = 0
#     total_count = 0

#     for box in boxes:
#         # Bounding box coordinates
#         xyxy = box.xyxy[0].tolist()
#         x1, y1, x2, y2 = map(int, xyxy)

#         # Crop object
#         cropped = image.crop((x1, y1, x2, y2))
#         cropped_path = os.path.join(user_dir, f"crop_{uuid.uuid4()}.jpg")
#         cropped.save(cropped_path)

#         # Classify
#         cls_result = classify_model(cropped_path)[0]
#         if len(cls_result.names) > 0:
#             predicted_class = cls_result.names[int(cls_result.probs.top1)]
#         else:
#             predicted_class = "unknown"

#         total_count += 1

#         # Check correctness
#         if predicted_class.upper() != expected_type.upper():
#             incorrect_count += 1
#             draw.rectangle([x1, y1, x2, y2], outline="red", width=6)
#             draw.text((x1, y1), f"{predicted_class}", fill="red")
#         else:
#             draw.rectangle([x1, y1, x2, y2], outline="yellow", width=6)
#             draw.text((x1, y1), f"{predicted_class}", fill="yellow")

#         # Cleanup
#         os.remove(cropped_path)

#     # Save annotated image
#     processed_filename = f"processed_{original_filename}"
#     processed_path = os.path.join(user_dir, processed_filename)
#     image.save(processed_path)

#     return {
#         "file_id": file_id,
#         "original_filename": original_filename,
#         "processed_filename": processed_filename,
#         "original_path": original_path,
#         "processed_path": processed_path,
#         "timestamp": timestamp,
#         "incorrect_count": incorrect_count,
#         "total_count": total_count
#     }







# ############## Old logic for annotation (if needed in future) ###############

# def annotate_image(image, boxes, classify_model):
#     for box in boxes:
#         x1, y1, x2, y2 = map(int, box[:4])
#         roi = image[y1:y2, x1:x2]
#         class_name, _ = run_classification(classify_model, roi)

#         if class_name:
#             label = f"{class_name}"

#             # Color: Teal (can adjust)
#             box_color = (0, 140, 255)

#             # Draw rounded rectangle manually (or normal rectangle)
#             cv2.rectangle(image, (x1, y1), (x2, y2), box_color, thickness=3)

#             # Label background
#             (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
#             cv2.rectangle(image, (x1, y1 - text_height - 10), (x1 + text_width + 10, y1), box_color, -1)

#             # Text on top
#             cv2.putText(image, label, (x1 + 5, y1 - 5),
#                         cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

#     return image

# def process_image(upload_file, user_email:None, detect_model, classify_model):
#     user_dir = create_user_dir(user_email)
#     file_id = str(uuid.uuid4())
#     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#     original_filename = generate_timestamped_filename(upload_file.filename, file_id, timestamp)
#     processed_filename = f"processed_{original_filename}"

#     original_path = os.path.join(user_dir, original_filename)
#     processed_path = os.path.join(user_dir, processed_filename)

#     save_upload_file(upload_file, original_path)

#     image = cv2.imread(original_path)
#     if image is None:
#         raise ValueError("Failed to read uploaded image")

#     boxes = run_detection(detect_model, image)
#     annotated_image = annotate_image(image, boxes, classify_model)
#     cv2.imwrite(processed_path, annotated_image)

#     return file_id, original_filename, processed_filename, original_path, processed_path, timestamp

