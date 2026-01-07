import cv2

def classify_objects(image, output_image, boxes, model):
    for box in boxes:
        x1, y1, x2, y2 = map(int, box[:4])
        roi = image[y1:y2, x1:x2]
        results = model(roi, verbose=False)
        if results and results[0].probs:
            probs = results[0].probs
            top_class = probs.top1
            class_name = model.names[top_class]
            confidence = probs.data[top_class].item()
            label = f"{class_name} {confidence:.2f}"
            cv2.rectangle(output_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(output_image, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return output_image
