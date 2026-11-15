let cameraStream = null;

async function startCamera() {
  const video = document.getElementById("camera");
  const status = document.getElementById("cameraStatus");
  if (!video) return;
  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Camera access requires HTTPS or localhost and a supported browser.");
    }
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false
    });
    video.srcObject = cameraStream;
    await video.play();
    if (status) status.textContent = "Camera is ready.";
  } catch (err) {
    if (status) status.textContent = "Camera error: " + err.message;
  }
}

function captureDataUrl() {
  const video = document.getElementById("camera");
  const canvas = document.getElementById("captureCanvas");
  if (!video || !canvas || !video.videoWidth) {
    throw new Error("Start the camera first.");
  }
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.85);
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-camera-start]").forEach(btn => {
    btn.addEventListener("click", startCamera);
  });

  document.querySelectorAll("[data-camera-capture]").forEach(btn => {
    btn.addEventListener("click", () => {
      const status = document.getElementById("cameraStatus");
      try {
        document.getElementById("faceImage").value = captureDataUrl();
        if (status) status.textContent = "Face image captured. You can register the student.";
      } catch (err) {
        if (status) status.textContent = err.message;
      }
    });
  });

  const recognizeButton = document.getElementById("recognizeButton");
  if (recognizeButton) {
    recognizeButton.addEventListener("click", async () => {
      const status = document.getElementById("cameraStatus");
      const result = document.getElementById("recognitionResult");
      recognizeButton.disabled = true;
      try {
        const image = captureDataUrl();
        status.textContent = "Checking face...";
        const response = await fetch(recognizeButton.dataset.recognizeUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image })
        });
        const data = await response.json();
        result.textContent = data.message + (data.student ? ` Student: ${data.student} (${data.student_id})` : "");
        result.className = "result " + (data.ok ? "success" : "warning");
        status.textContent = data.ok ? "Recognition completed." : "Please try again.";
      } catch (err) {
        result.textContent = err.message;
        result.className = "result warning";
      } finally {
        recognizeButton.disabled = false;
      }
    });
  }
});
