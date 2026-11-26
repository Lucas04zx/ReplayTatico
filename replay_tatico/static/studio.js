import { drawEffects } from "./effects.js";

const byId = (id) => document.getElementById(id);
const select = byId("clips");
const timeline = byId("timeline");
const screen = byId("screen");
const image = byId("frame");
const motion = byId("motion");
const canvas = byId("effect");
const play = byId("play");
const tabs = [...document.querySelectorAll("[data-view]")];
const manualNames = { SHOT: "Chute energético", SAVE: "Mão Fantasma", GOAL: "Gol especial", INTERCEPTION: "Interceptação" };
const depthNames = { saida: "Saída", trajetoria: "Trajetória", recepcao: "Recepção", inicio_amostra: "Início da amostra", meio_amostra: "Meio da amostra", fim_amostra: "Fim da amostra" };

let meta;
let current = 0;
let visible = null;
let view = "original";
let playing = false;
let nativePlayback = false;
let timer;
let playbackId = 0;
let requestId = 0;
let catalogId = 0;
let marking = null;
let reference = {};
let manual = [];

const say = (message = "") => { byId("notification").textContent = message; };
const base = () => "/api/clipes/" + encodeURIComponent(meta.id);
const forAnnotation = () => meta?.id === "avaliacao";

async function api(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const problem = response.headers.get("Content-Type")?.includes("json") ? await response.json() : {};
    throw Error(problem.error || `A operação falhou (HTTP ${response.status}).`);
  }
  return response.json();
}

function stop() {
  ++playbackId;
  playing = false;
  nativePlayback = false;
  clearTimeout(timer);
  motion.pause();
  motion.hidden = true;
  play.textContent = "▶";
  play.setAttribute("aria-label", "Reproduzir");
}

function updateMode() {
  for (const tab of tabs) tab.setAttribute("aria-pressed", String(tab.dataset.view === view));
  byId("layers").hidden = view !== "technical" || !meta?.has_analysis;
  byId("special").hidden = view !== "special" || !meta;
  canvas.hidden = view !== "special";
  byId("overview").hidden = forAnnotation();
  byId("annotation").hidden = !forAnnotation();
}

function drawCurrentEffects() {
  if (meta && visible !== null && view === "special") {
    drawEffects(canvas, meta, [...meta.events, ...manual], visible, Number(byId("intensity").value));
  }
}

function displayIndex(index) {
  visible = index;
  timeline.value = String(index);
  byId("counter").textContent = `Q ${index} / ${meta.end}  ·  ${(index / meta.fps).toFixed(2)} s`;
  drawCurrentEffects();
  renderMarker();
}

function renderMarker() {
  const marker = byId("selection");
  const point = visible === reference.release - 1 ? reference.passer
    : visible === reference.reception ? reference.receiver : null;
  marker.hidden = !point || !forAnnotation();
  if (marker.hidden) return;
  const rectangle = videoRectangle();
  marker.style.left = (rectangle.x + point[0] / meta.width * rectangle.width) + "px";
  marker.style.top = (rectangle.y + point[1] / meta.height * rectangle.height) + "px";
}

function activeLayers() {
  return [...byId("layers").querySelectorAll("input:checked")].map((item) => item.value);
}

function frameUrl(index) {
  const params = new URLSearchParams({
    view: view === "technical" ? "technical" : "original",
    layers: view === "technical" ? activeLayers().join(",") : "",
    full: forAnnotation() ? "1" : "0",
  });
  return base() + "/quadros/" + index + "?" + params;
}

async function showFrame(index) {
  if (!meta) return;
  current = Math.max(meta.start, Math.min(meta.end, index));
  timeline.value = String(current);
  const requested = current;
  const identity = ++requestId;
  const next = new Image();
  next.src = frameUrl(requested);
  try {
    await next.decode();
  } catch {
    if (identity === requestId) {
      stop();
      say(`Falha ao ler o quadro ${requested}.`);
    }
    return;
  }
  if (identity !== requestId) return;
  image.src = next.src;
  image.hidden = false;
  byId("empty").hidden = true;
  displayIndex(requested);
}

async function tick(identity) {
  if (!playing || !meta || identity !== playbackId) return;
  if (current >= meta.end) { stop(); return; }
  const time = performance.now();
  await showFrame(current + 1);
  if (playing && identity === playbackId) {
    timer = setTimeout(() => tick(identity), Math.max(0, 1000 / meta.fps / Number(byId("speed").value) - (performance.now() - time)));
  }
}

async function startPlayback() {
  const identity = ++playbackId;
  const technical = view === "technical";
  if (technical && activeLayers().length !== byId("layers").querySelectorAll("input").length) {
    tick(identity);
    return;
  }
  const origin = technical ? meta.start : 0;
  const url = base() + "/video" + (technical ? "?view=technical" : "");
  if (motion.getAttribute("src") !== url) motion.src = url;
  motion.currentTime = (current - origin) / meta.fps;
  motion.playbackRate = Number(byId("speed").value);
  try {
    nativePlayback = true;
    motion.hidden = false;
    await motion.play();
    if (!playing || !nativePlayback || identity !== playbackId) return;
    const onFrame = (_, data) => {
      if (!playing || !nativePlayback || identity !== playbackId) return;
      current = Math.min(meta.end, Math.round(data.mediaTime * meta.fps) + origin);
      displayIndex(current);
      if (current >= meta.end) {
        move(meta.end);
        return;
      }
      if (motion.requestVideoFrameCallback) motion.requestVideoFrameCallback(onFrame);
      else requestAnimationFrame((time) => onFrame(time, { mediaTime: motion.currentTime }));
    };
    if (motion.requestVideoFrameCallback) motion.requestVideoFrameCallback(onFrame);
    else requestAnimationFrame((time) => onFrame(time, { mediaTime: motion.currentTime }));
  } catch {
    if (identity !== playbackId) return;
    nativePlayback = false;
    motion.hidden = true;
    if (playing) tick(identity);
  }
}

function move(index) {
  stop();
  return showFrame(index);
}

function listMarkers() {
  const markers = byId("markers");
  const manualEvents = byId("manual-events");
  markers.replaceChildren();
  manualEvents.replaceChildren();
  for (const event of [...meta.events, ...manual]) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.event = event.type;
    const label = event.type === "PASS_START" ? "Saída" : event.type === "PASS_RECEIVED" ? "Recepção" : manualNames[event.type];
    button.textContent = event.origin === "manual" ? "▲" : label;
    button.title = `${label} · ${event.origin} · quadro ${event.frame}`;
    const percent = 100 * (event.frame - meta.start) / Math.max(1, meta.end - meta.start);
    button.style.left = Math.max(2, Math.min(98, percent)) + "%";
    button.addEventListener("click", () => move(event.frame));
    markers.append(button);
  }
  for (const event of manual) {
    const item = document.createElement("li");
    item.append(`${manualNames[event.type]} · Q ${event.frame} · manual`);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "button";
    remove.textContent = "Remover";
    remove.addEventListener("click", () => {
      manual = manual.filter((candidate) => candidate !== event);
      persistManual();
    });
    item.append(remove);
    manualEvents.append(item);
  }
}

function persistManual() {
  try { localStorage.setItem("replay-effects/" + meta.id, JSON.stringify(manual)); }
  catch { say("As marcações ficarão disponíveis nesta sessão."); }
  listMarkers();
  drawCurrentEffects();
}

function renderDetails() {
  const result = meta.pass;
  byId("pass-status").textContent = result ? (result.status === "CONCLUIDO" ? "Passe concluído" : "Passe inconclusivo") : "Este clipe ainda não foi processado.";
  byId("reason").textContent = result?.reason || "";
  const fields = byId("pass-fields");
  fields.replaceChildren();
  if (result) {
    for (const [name, value] of [["Passador", result.passer], ["Recebedor", result.receiver], ["Saída", result.release],
      ["Recepção", result.reception], ["Duração", result.seconds == null ? null : `${result.seconds.toFixed(3)} s`]]) {
      const title = document.createElement("dt");
      const text = document.createElement("dd");
      title.textContent = name;
      text.textContent = value ?? "—";
      fields.append(title, text);
    }
  }
  byId("export").hidden = !meta.has_analysis;
  const downloads = byId("downloads");
  downloads.replaceChildren();
  if (meta.has_analysis) {
    const files = [["Replay MP4", "replay.mp4"], ["CSV", "resultado.csv"], ["Análise JSON", "analise.json"]];
    if (meta.comparison) files.push(["Comparação manual", "avaliacao.json"]);
    if (meta.depth_origin === "manual") files.push(["Replay com referência", "replay-referencia.mp4"]);
    for (const [text, file] of files) {
      const link = document.createElement("a");
      link.className = "button";
      link.textContent = text;
      link.href = base() + "/exportar/" + file;
      downloads.append(link);
    }
  }
  byId("depth").hidden = !meta.depth?.length;
  const grid = byId("depth-grid");
  grid.replaceChildren();
  if (meta.depth) {
    const fromReference = meta.depth_origin === "manual";
    const query = fromReference ? "?origem=manual" : "";
    byId("depth-title").textContent = fromReference ? "Profundidade · quadros da referência manual" : "Profundidade monocular";
    byId("depth-table").href = base() + "/evidencias/profundidade.csv" + query;
    for (const entry of meta.depth) {
      const figure = document.createElement("figure");
      const caption = document.createElement("figcaption");
      caption.textContent = `${depthNames[entry.name]} · quadro ${entry.frame}`;
      figure.append(caption);
      for (const [file, label] of [[entry.rgb, "Quadro RGB"], [entry.map, "Mapa de profundidade"]]) {
        const evidence = new Image();
        evidence.loading = "lazy";
        evidence.alt = label;
        evidence.src = base() + "/evidencias/" + encodeURIComponent(file) + query;
        figure.append(evidence);
      }
      grid.append(figure);
    }
  }
}

async function loadClip(id) {
  stop();
  ++requestId;
  const selection = ++catalogId;
  meta = null;
  visible = null;
  setMarking(null);
  image.hidden = true;
  byId("empty").hidden = false;
  byId("empty").textContent = id ? "Carregando quadro…" : "Selecione ou importe um vídeo.";
  if (!id) return;
  const loaded = await api("/api/clipes/" + encodeURIComponent(id));
  if (catalogId !== selection) return;
  meta = loaded;
  reference = {};
  view = meta.has_analysis ? "technical" : "original";
  try { manual = JSON.parse(localStorage.getItem("replay-effects/" + meta.id) || "[]"); }
  catch { manual = []; }
  if (!Array.isArray(manual)) manual = [];
  if (forAnnotation()) manual = [];
  tabs.find((item) => item.dataset.view === "technical").disabled = !meta.has_analysis;
  tabs.find((item) => item.dataset.view === "special").disabled = forAnnotation();
  timeline.disabled = false;
  timeline.min = String(meta.start);
  timeline.max = String(meta.end);
  screen.style.aspectRatio = `${meta.width} / ${meta.height}`;
  canvas.width = meta.width;
  canvas.height = meta.height;
  byId("annotation-help").textContent = meta.reference_saved ? "A referência deste trecho já foi registrada."
    : "Registre a saída e marque o passador no quadro anterior. Registre a recepção e marque o recebedor no quadro do primeiro contato.";
  renderReference();
  updateMode();
  renderDetails();
  listMarkers();
  await showFrame(meta.start);
}

async function catalog(preferred) {
  const choices = await api("/api/clipes");
  const queryClip = new URLSearchParams(location.search).get("clipe");
  select.replaceChildren();
  for (const choice of choices) select.add(new Option(choice.label, choice.id));
  if (!choices.length) select.add(new Option("Nenhum vídeo disponível", ""));
  const id = [preferred, queryClip, choices.find((item) => item.id.startsWith("run-"))?.id, choices[0]?.id]
    .find((candidate) => choices.some((item) => item.id === candidate));
  select.value = id || "";
  await loadClip(id);
}

function setMarking(type) {
  marking = type;
  screen.classList.toggle("marking", Boolean(type));
}

function videoRectangle() {
  const screenWidth = screen.clientWidth;
  const screenHeight = screen.clientHeight;
  const ratio = Math.min(screenWidth / meta.width, screenHeight / meta.height);
  return { x: (screenWidth - meta.width * ratio) / 2, y: (screenHeight - meta.height * ratio) / 2,
    width: meta.width * ratio, height: meta.height * ratio };
}

function renderReference() {
  const { release, reception, passer, receiver } = reference;
  byId("annotation-summary").textContent = `Saída ${release ?? "—"} · Passador ${passer ? "marcado" : "—"} · Recepção ${reception ?? "—"} · Recebedor ${receiver ? "marcado" : "—"}`;
  for (const button of ["mark-release", "mark-reception"]) byId(button).disabled = Boolean(meta?.reference_saved);
  byId("save-reference").disabled = Boolean(meta?.reference_saved) || !passer || !receiver || reception <= release;
  renderMarker();
}

select.addEventListener("change", () => { say(); loadClip(select.value).catch((error) => say(error.message)); });
timeline.addEventListener("input", () => move(Number(timeline.value)));
byId("previous").addEventListener("click", () => move(current - 1));
byId("next").addEventListener("click", () => move(current + 1));
play.addEventListener("click", async () => {
  if (!meta) return;
  if (playing) { move(current); return; }
  if (current === meta.end) await showFrame(meta.start);
  playing = true;
  play.textContent = "❚❚";
  play.setAttribute("aria-label", "Pausar");
  startPlayback();
});
motion.addEventListener("ended", () => { if (nativePlayback) move(meta.end); });
byId("speed").addEventListener("change", () => {
  if (nativePlayback) motion.playbackRate = Number(byId("speed").value);
});
document.addEventListener("keydown", (event) => {
  if (!meta || ["INPUT", "SELECT", "BUTTON", "TEXTAREA"].includes(event.target.tagName)) return;
  if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
    event.preventDefault();
    move(current + (event.key === "ArrowLeft" ? -1 : 1));
  } else if (event.code === "Space") {
    event.preventDefault();
    play.click();
  }
});
for (const tab of tabs) tab.addEventListener("click", () => {
  if (!meta) return;
  view = tab.dataset.view;
  setMarking(null);
  updateMode();
  move(current);
});
byId("layers").addEventListener("change", () => move(current));
byId("intensity").addEventListener("input", drawCurrentEffects);
byId("manual-mark").addEventListener("click", () => {
  if (!meta || visible === null) return;
  move(visible);
  setMarking("manual");
});
byId("mark-release").addEventListener("click", () => {
  if (visible === null || visible <= meta.start) { say("Avance pelo menos um quadro para marcar a saída."); return; }
  reference.release = visible;
  delete reference.passer;
  setMarking("passer");
  say("Clique no tronco do passador no quadro anterior à saída.");
  move(visible - 1);
  renderReference();
});
byId("mark-reception").addEventListener("click", () => {
  if (visible === null) return;
  move(visible);
  reference.reception = visible;
  delete reference.receiver;
  setMarking("receiver");
  say("Clique no tronco do recebedor no quadro do primeiro contato.");
  renderReference();
});
screen.addEventListener("click", (event) => {
  if (!marking || !meta || visible !== current || image.hidden) return;
  const rect = screen.getBoundingClientRect();
  const box = videoRectangle();
  const x = (event.clientX - rect.left - box.x) / box.width;
  const y = (event.clientY - rect.top - box.y) / box.height;
  if (x < 0 || y < 0 || x >= 1 || y >= 1) return;
  const xy = [x * meta.width, y * meta.height];
  if (marking === "manual") {
    manual.push({ type: byId("manual-type").value, frame: visible, position: xy, origin: "manual" });
    persistManual();
  } else {
    const expected = marking === "passer" ? reference.release - 1 : reference.reception;
    if (visible !== expected) { say(`Volte ao quadro ${expected} para posicionar o marcador.`); return; }
    reference[marking] = xy;
    renderReference();
  }
  setMarking(null);
  say();
});
byId("save-reference").addEventListener("click", async () => {
  try {
    await api("/api/avaliacao/referencia", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(reference),
    });
    meta.reference_saved = true;
    byId("annotation-help").textContent = "Referência salva. O trecho pode ser avaliado pela CLI.";
    renderReference();
    say("Marcação independente registrada.");
  } catch (error) { say(error.message); }
});
byId("import-form").addEventListener("change", async (event) => {
  if (!event.target.files.length) return;
  say("Importando vídeo…");
  try {
    const result = await api("/api/importar", { method: "POST", body: new FormData(byId("import-form")) });
    await catalog(result.id);
    say("Vídeo disponível para inspeção.");
  } catch (error) { say(error.message); }
  event.target.value = "";
});
window.addEventListener("resize", renderMarker);
catalog().catch((error) => say(error.message));
