def detect_objects(image, model):
    results = model(image, conf=0.75, iou=0.75, verbose=False)
    if hasattr(results[0], "boxes") and results[0].boxes is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        if len(boxes) > 0:
            return boxes

    return []





