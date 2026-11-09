/* Borne de pointage : détecte un visage, envoie son empreinte au serveur et affiche le résultat. */
(function () {
  const cfg = JSON.parse(document.getElementById("kiosk-config").textContent);
  const $ = (id) => document.getElementById(id);
  const video = $("kiosk-video");
  const canvas = $("kiosk-canvas");
  const statusEl = $("kiosk-status");
  const resultCard = $("kiosk-result");

  let busy = false;
  let stable = 0;
  let cooldownUntil = 0;

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function setResult(state, title, name, details) {
    resultCard.dataset.state = state;
    $("result-title").textContent = title;
    $("result-name").textContent = name || "";
    $("result-details").textContent = details || "";
  }

  function renderRecent(rows) {
    const body = $("recent-body");
    body.innerHTML = "";
    if (!rows || !rows.length) {
      body.innerHTML = '<tr><td colspan="3" class="px-4 py-6 text-center text-slate-400">Aucun pointage aujourd\'hui.</td></tr>';
      return;
    }
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.className = "border-y border-transparent border-b-slate-200 dark:border-b-navy-500";
      [row.name, row.action, row.time].forEach((value, index) => {
        const td = document.createElement("td");
        td.className = "whitespace-nowrap px-4 py-2" + (index === 0 ? " font-medium" : "");
        td.textContent = value;
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
  }

  function tickClock() {
    const now = new Date();
    $("kiosk-clock").textContent = now.toLocaleTimeString("fr-FR");
    $("kiosk-date").textContent = now.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  }
  tickClock();
  setInterval(tickClock, 1000);

  function handleResult(r, box) {
    const label = r.employee ? r.employee.name + (r.confidence ? " (" + r.confidence + "%)" : "") : "";
    if (r.status === "in" || r.status === "out") {
      RucheFace.drawBox(canvas, box, "#10b981", label);
      const title = r.status === "in" ? "Arrivée enregistrée !" : "Départ enregistré !";
      let details = r.date + " à " + r.time;
      if (r.status === "in" && r.late_minutes) details += " — retard de " + r.late_minutes + " min";
      setResult("success", title, r.employee.name, details);
      setStatus(title);
      renderRecent(r.recent);
      cooldownUntil = Date.now() + 3500;
    } else if (r.status === "duplicate") {
      RucheFace.drawBox(canvas, box, "#f59e0b", label);
      setResult("warning", "Déjà pointé", r.employee ? r.employee.name : "", r.message);
      setStatus(r.message);
      cooldownUntil = Date.now() + 2500;
    } else if (r.status === "inactive") {
      RucheFace.drawBox(canvas, box, "#ef4444", label);
      setResult("error", "Pointage refusé", r.employee ? r.employee.name : "", r.message);
      setStatus(r.message);
      cooldownUntil = Date.now() + 3000;
    } else if (r.status === "unknown") {
      RucheFace.drawBox(canvas, box, "#ef4444", "Non reconnu");
      setResult("error", "Visage non reconnu", "", "Réessayez ou contactez le service RH.");
      setStatus("Visage non reconnu.");
      cooldownUntil = Date.now() + 2500;
    } else {
      setResult("error", "Erreur", "", r.message || "Une erreur est survenue.");
      setStatus(r.message || "Erreur.");
      cooldownUntil = Date.now() + 3000;
    }
  }

  async function submit(detection) {
    busy = true;
    setStatus("Analyse en cours…");
    try {
      const response = await RucheFace.postJSON(cfg.scanUrl, { descriptor: Array.from(detection.descriptor) });
      handleResult(response, detection.detection.box);
    } catch (e) {
      setResult("error", "Erreur réseau", "", "Impossible de joindre le serveur.");
      setStatus("Impossible de joindre le serveur.");
      cooldownUntil = Date.now() + 3000;
    } finally {
      busy = false;
    }
  }

  async function loop() {
    try {
      if (Date.now() >= cooldownUntil && !busy) {
        const detection = await RucheFace.detect(video);
        if (detection) {
          const box = detection.detection.box;
          const closeEnough = box.width >= video.videoWidth * 0.18;
          RucheFace.drawBox(canvas, box, closeEnough ? "#4467EF" : "#f59e0b", closeEnough ? "" : "Rapprochez-vous");
          stable = closeEnough ? stable + 1 : 0;
          if (stable >= 2) {
            stable = 0;
            await submit(detection);
          } else if (!closeEnough) {
            setStatus("Rapprochez-vous de la caméra.");
          }
        } else {
          stable = 0;
          RucheFace.clear(canvas);
          setStatus("Placez votre visage devant la caméra.");
          if (resultCard.dataset.state !== "idle") setResult("idle", "En attente", "", "Placez-vous devant la caméra pour pointer.");
        }
      }
    } catch (e) {
      console.error(e);
    }
    setTimeout(loop, 350);
  }

  (async function start() {
    try {
      setStatus("Chargement des modèles de reconnaissance…");
      await RucheFace.loadModels();
      setStatus("Démarrage de la caméra…");
      await RucheFace.startCamera(video);
      RucheFace.sizeCanvas(video, canvas);
      setStatus("Placez votre visage devant la caméra.");
      loop();
    } catch (e) {
      console.error(e);
      setStatus(e && e.message ? e.message : "Caméra indisponible.");
      setResult("error", "Caméra indisponible", "", e && e.message ? e.message : "Autorisez l'accès à la caméra.");
    }
  })();
})();
