/* Utilitaires partagés par la borne de pointage et l'enrôlement (face-api.js, 100 % dans le navigateur). */
(function () {
  const script = document.currentScript;
  const modelsUrl = script.dataset.modelsUrl;

  async function loadModels() {
    await Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri(modelsUrl),
      faceapi.nets.faceLandmark68Net.loadFromUri(modelsUrl),
      faceapi.nets.faceRecognitionNet.loadFromUri(modelsUrl),
    ]);
  }

  async function startCamera(video) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("La caméra n'est accessible qu'en HTTPS (ou sur localhost).");
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    return stream;
  }

  const detectorOptions = () => new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.5 });

  function detect(video) {
    return faceapi.detectSingleFace(video, detectorOptions()).withFaceLandmarks().withFaceDescriptor();
  }

  function sizeCanvas(video, canvas) {
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
  }

  function clear(canvas) {
    canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
  }

  function drawBox(canvas, box, color, label) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.lineWidth = Math.max(3, canvas.width / 200);
    ctx.strokeStyle = color;
    ctx.strokeRect(box.x, box.y, box.width, box.height);
    if (label) {
      const size = Math.max(16, canvas.width / 36);
      ctx.font = "600 " + size + "px Poppins, Arial, sans-serif";
      const textWidth = ctx.measureText(label).width + 20;
      const height = size + 14;
      const x = Math.max(0, Math.min(box.x, canvas.width - textWidth));
      const y = Math.max(0, box.y - height);
      ctx.fillStyle = color;
      ctx.fillRect(x, y, textWidth, height);
      ctx.fillStyle = "#fff";
      ctx.textBaseline = "middle";
      ctx.fillText(label, x + 10, y + height / 2);
    }
  }

  function getCookie(name) {
    const match = document.cookie.split("; ").find((row) => row.startsWith(name + "="));
    return match ? decodeURIComponent(match.split("=")[1]) : "";
  }

  async function postJSON(url, data) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
      body: JSON.stringify(data),
    });
    let body = {};
    try {
      body = await response.json();
    } catch (e) {
      body = { status: "error", message: "Réponse invalide du serveur." };
    }
    body.httpStatus = response.status;
    return body;
  }

  window.RucheFace = { loadModels, startCamera, detect, sizeCanvas, clear, drawBox, postJSON };
})();
