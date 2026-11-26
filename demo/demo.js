// A demonstração desenha observações gravadas nas coordenadas do vídeo de origem.
const palette = {
  passer: "#ff9b4a", receiver: "#76cfff", other: "#cbd9ca",
  near: "#55b6a8", far: "#f0c561",
};
const once = new Map();

function asset(name) {
  return new URL("../data/" + name, import.meta.url).href;
}

export const catalogUrl = asset("clipes.json");
export const clipUrl = (id) => asset(encodeURIComponent(id) + ".json");
export const depthUrl = (id) => asset(encodeURIComponent(id) + "-profundidade.csv");
export const exportsFor = (meta) => [
  ["CSV", asset(encodeURIComponent(meta.id) + "-resultado.csv")],
  ["Observações JSON", clipUrl(meta.id)],
];

function pitch(w, h) {
  const key = w + "×" + h;
  if (once.has(key)) return once.get(key);
  const image = document.createElement("canvas");
  image.width = w;
  image.height = h;
  const ctx = image.getContext("2d");
  ctx.scale(w / 1000, h / 560);
  const sky = ctx.createLinearGradient(0, 0, 0, 560);
  sky.addColorStop(0, "#171f25");
  sky.addColorStop(1, "#152e23");
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, 1000, 560);

  for (let stripe = 0; stripe < 12; stripe += 1) {
    const left = stripe / 12;
    const right = (stripe + 1) / 12;
    ctx.fillStyle = stripe % 2 === 0 ? "#2b533a" : "#305d42";
    ctx.beginPath();
    ctx.moveTo(130 + left * 740, 132);
    ctx.lineTo(130 + right * 740, 132);
    ctx.lineTo(-90 + right * 1180, 514);
    ctx.lineTo(-90 + left * 1180, 514);
    ctx.closePath();
    ctx.fill();
  }
  ctx.strokeStyle = "#a0bb9e";
  ctx.lineWidth = 2;
  ctx.beginPath();
  const markings = [
    [[130, 132], [870, 132], [1090, 514], [-90, 514], [130, 132]],
    [[500, 132], [500, 514]],
    [[75, 227], [225, 227], [172, 426], [-39, 426]],
    [[925, 227], [775, 227], [828, 426], [1039, 426]],
    [[112, 167], [888, 167]],
  ];
  for (const [first, ...rest] of markings) {
    ctx.moveTo(...first);
    for (const point of rest) ctx.lineTo(...point);
  }
  ctx.moveTo(576, 306);
  ctx.ellipse(500, 306, 76, 49, 0, 0, Math.PI * 2);
  ctx.stroke();
  ctx.strokeStyle = "#28383a";
  for (let row = 30; row <= 110; row += 16) {
    ctx.beginPath();
    for (let col = 16; col < 1000; col += 32) {
      ctx.moveTo(col, row);
      ctx.lineTo(col + 25, row);
    }
    ctx.stroke();
  }
  once.set(key, image);
  return image;
}

function text(ctx, label, x, y, color = "#f4f2e8", size = 26) {
  ctx.font = `700 ${size}px "Segoe UI", sans-serif`;
  ctx.lineWidth = 4;
  ctx.strokeStyle = "#101b16";
  ctx.strokeText(label, x, y);
  ctx.fillStyle = color;
  ctx.fillText(label, x, y);
}

function dot(ctx, x, y, radius, color) {
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

function marker(ctx, box, color) {
  const [x1, y1, x2, y2] = box;
  const h = y2 - y1;
  const w = (x2 - x1) * .6;
  const x = (x1 + x2) / 2;
  dot(ctx, x, y1 + .15 * h, Math.max(2, .10 * h), color);
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(2, .07 * h);
  ctx.beginPath();
  ctx.moveTo(x, y1 + .48 * h);
  ctx.lineTo(x - .30 * w, y2);
  ctx.moveTo(x, y1 + .48 * h);
  ctx.lineTo(x + .30 * w, y2);
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.fillRect(x - w / 2, y1 + .27 * h, w, .32 * h);
}

function roleColor(track, roles) {
  if (Number(track) === roles.passer) return palette.passer;
  if (Number(track) === roles.receiver) return palette.receiver;
  return palette.other;
}

function outline(ctx, polygons, color) {
  ctx.save();
  ctx.fillStyle = color;
  ctx.strokeStyle = color;
  for (const [first, ...points] of polygons) {
    if (!first) continue;
    ctx.beginPath();
    ctx.moveTo(...first);
    for (const point of points) ctx.lineTo(...point);
    ctx.closePath();
    ctx.globalAlpha = .45;
    ctx.fill();
    ctx.globalAlpha = .95;
    ctx.lineWidth = 2.5;
    ctx.stroke();
  }
  ctx.restore();
}

function lowerBody(ctx, pose, minimum) {
  if (!pose) return;
  ctx.lineWidth = 3;
  ctx.lineCap = "round";
  ctx.strokeStyle = palette.passer;
  for (const [a, b] of [[0, 1], [1, 2], [3, 4], [4, 5]]) {
    if (Math.min(pose[a][2], pose[b][2]) < minimum) continue;
    ctx.beginPath();
    ctx.moveTo(pose[a][0], pose[a][1]);
    ctx.lineTo(pose[b][0], pose[b][1]);
    ctx.stroke();
  }
  for (const [x, y, confidence] of pose) {
    if (confidence >= minimum) dot(ctx, x, y, 4, "#ffdb90");
  }
}

function trail(ctx, meta, index) {
  ctx.strokeStyle = palette.passer;
  ctx.lineWidth = 4;
  ctx.beginPath();
  for (let previous = Math.max(meta.start + 1, index - 29); previous <= index; previous += 1) {
    const from = meta.ball[previous - 1];
    const to = meta.ball[previous];
    if (!from || !to) continue;
    ctx.moveTo(...from);
    ctx.lineTo(...to);
  }
  ctx.stroke();
}

export function drawFrame(canvas, meta, index, view, layers) {
  const ctx = canvas.getContext("2d");
  const frame = meta.frames[index - meta.start];
  const roles = meta.reference || meta.pass;
  const technical = view === "technical";
  ctx.drawImage(pitch(meta.width, meta.height), 0, 0);
  for (const [track, box] of Object.entries(frame.players)) {
    const color = technical || view === "special" ? roleColor(track, roles) : palette.other;
    marker(ctx, box, color);
    if (technical && layers.has("mask") && frame.masks?.[track]) outline(ctx, frame.masks[track], color);
    if (technical && layers.has("boxes")) {
      const [x1, y1, x2, y2] = box;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      text(ctx, "#" + track, x1, y1 - 5, color, 17);
    }
  }
  if (technical && layers.has("pose") && Math.abs(index - (roles.release ?? Infinity)) <= 12) {
    lowerBody(ctx, frame.pose, meta.pose_conf);
  }
  if (technical && layers.has("ball")) trail(ctx, meta, index);
  if (frame.ball) dot(ctx, ...frame.ball, 6, "#f9f5e5");
  if (technical && layers.has("hud")) {
    text(ctx, frame.ball ? "Bola detectada" : "Bola sem detecção", 26, 44);
    const event = meta.events.find((candidate) => candidate.frame === index);
    if (event) text(ctx, `Q ${index} · ${event.origin}`, 26, 78, "#f5cd60", 23);
  }
  text(ctx, "RECONSTRUÇÃO ESQUEMÁTICA", 26, meta.height - 35, "#e4eada", 26);
}

export function attachDepth(figure, meta, entry) {
  const canvas = document.createElement("canvas");
  canvas.width = 480;
  canvas.height = 270;
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", `Mapa esquemático de profundidade do quadro ${entry.frame}`);
  const ctx = canvas.getContext("2d");
  const frame = meta.frames[entry.frame - meta.start];
  ctx.drawImage(pitch(480, 270), 0, 0);
  ctx.fillStyle = "#091411b8";
  ctx.fillRect(0, 0, 480, 270);
  const list = document.createElement("ul");
  list.className = "depth-measures";
  const measured = entry.samples.filter((sample) => sample.median !== null);
  const nearer = Math.min(...measured.map((sample) => sample.median));
  for (const sample of measured) {
    const near = sample.median === nearer;
    const color = near ? palette.near : palette.far;
    const box = frame.players[sample.id];
    if (box) {
      const x = (box[0] + box[2]) * .5 * 480 / meta.width;
      const y = (box[1] + box[3]) * .5 * 270 / meta.height;
      dot(ctx, x, y, 10, color);
      text(ctx, String(sample.id), x + 14, y + 5, color, 16);
    }
    const item = document.createElement("li");
    item.style.setProperty("--depth-color", color);
    item.textContent = `ID ${sample.id} · ${sample.role} · ${sample.median.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} · ${near ? "mais próximo" : "mais distante"}`;
    list.append(item);
  }
  figure.append(canvas, list);
}
