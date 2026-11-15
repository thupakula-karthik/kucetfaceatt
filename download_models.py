import os
import urllib.request

os.makedirs("models", exist_ok=True)
models = {
    "face_detection_yunet_2023mar.onnx":
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx":
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}
for filename, url in models.items():
    path = os.path.join("models", filename)
    if not os.path.exists(path):
        print("Downloading", filename)
        urllib.request.urlretrieve(url, path)
print("Model download complete.")
