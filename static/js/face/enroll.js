/* Enrôlement : capture plusieurs échantillons du visage d'un employé puis les envoie au serveur. */
(function () {
  const cfg = JSON.parse(document.getElementById("enroll-config").textContent);
  const $ = (id) => document.getElementById(id);
  const video = $("enroll-video");
  const canvas = $("enroll-canvas");
  const statusEl = $("enroll-status");
  const startBtn = $("enroll-start");
  const consent = $("enroll-consent");
  const progress = $("enroll-progress");
  const TARGET = cfg.samples || 5;

  let ready = false;
  let capturing = false;
  const samples = [];
  let lastSample = 0;

  const setStatus = (text) => (statusEl.textContent = text);

  function updateButton() {
    startBtn.disabled = !ready || capturing || !consent.checked;
  }
  consent.addEventListener("change", updateButton);

  function renderProgress() {
    progress.textContent = samples.length + " / " + TARGET + " échantillons";
    $("enroll-bar").style.width = Math.round((samples.length / TARGET) * 100) + "%";
  }

  async function captureLoop() {
    if (!capturing) return;
    try {
      const detection = await RucheFace.detect(video);
      if (detection) {
        const box = detection.detection.box;
        const good = detection.detection.score >= 0.8 && box.width >= video.videoWidth * 0.25;
        RucheFace.drawBox(canvas, box, good ? "#10b981" : "#f59e0b", good ? "" : "Rapprochez-vous");
        if (good && Date.now() - lastSample > 700) {
          samples.push(Array.from(detection.descriptor));
          lastSample = Date.now();
          renderProgress();
          setStatus("Échantillon " + samples.length + " capturé. Tournez très légèrement la tête.");
        }
      } else {
        RucheFace.clear(canvas);
        setStatus("Aucun visage détecté : regardez la caméra.");
      }
      if (samples.length >= TARGET) {
        capturing = false;
        await save();
        return;
      }
    } catch (e) {
      console.error(e);
    }
    setTimeout(captureLoop, 300);
  }

  async function save() {
    setStatus("Enregistrement…");
    const response = await RucheFace.postJSON(cfg.saveUrl, { consent: true, descriptors: samples });
    if (response.status === "ok") {
      setStatus("Visage enregistré. Redirection…");
      window.location.href = response.redirect;
    } else {
      setStatus(response.message || "Échec de l'enregistrement.");
      samples.length = 0;
      renderProgress();
      updateButton();
    }
  }

  startBtn.addEventListener("click", () => {
    if (!consent.checked) return;
    samples.length = 0;
    renderProgress();
    capturing = true;
    updateButton();
    setStatus("Regardez la caméra…");
    captureLoop();
  });

  (async function init() {
    try {
      setStatus("Chargement des modèles de reconnaissance…");
      await RucheFace.loadModels();
      setStatus("Démarrage de la caméra…");
      await RucheFace.startCamera(video);
      RucheFace.sizeCanvas(video, canvas);
      ready = true;
      setStatus("Caméra prête. Cochez le consentement puis lancez la capture.");
      renderProgress();
      updateButton();
    } catch (e) {
      console.error(e);
      setStatus(e && e.message ? e.message : "Caméra indisponible.");
    }
  })();
})();
