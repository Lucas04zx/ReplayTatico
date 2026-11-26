const appearances = {
  PASS_START: { color: "#ffcc54", duration: .45 },
  PASS_RECEIVED: { color: "#70c7ff", duration: .55 },
  SHOT: { color: "#ff8041", duration: .75 },
  SAVE: { color: "#ffd55f", duration: 1.15 },
  GOAL: { color: "#ffdf76", duration: 1.2 },
  INTERCEPTION: { color: "#7cf6ec", duration: .62 },
};
const circle = Math.PI * 2;

function pulse(ctx, x, y, time, color, distance, intensity) {
  ctx.strokeStyle = color;
  ctx.lineWidth = (1 + (1 - time) * 4) * intensity;
  for (const delta of [0, .16]) {
    const progress = Math.max(0, time - delta);
    ctx.globalAlpha = (1 - time) * (delta ? .42 : .86);
    ctx.beginPath();
    ctx.ellipse(x, y, 10 + distance * progress, 6 + distance * progress * .56, 0, 0, circle);
    ctx.stroke();
  }
}

function sparks(ctx, x, y, progress, color, seed, spread, intensity) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 2 * intensity;
  ctx.globalAlpha = (1 - progress) * .9;
  for (let index = 0; index < 32; index += 1) {
    const angle = index * 2.39996 + seed * .13;
    const distance = (35 + (index * 13 % 63)) * progress * spread;
    const size = 3 + (index * 7 % 15) * (1 - progress);
    const dx = Math.cos(angle);
    const dy = Math.sin(angle) * .7;
    ctx.beginPath();
    ctx.moveTo(x + dx * distance, y + dy * distance + 18 * progress ** 2);
    ctx.lineTo(x + dx * (distance + size), y + dy * (distance + size) + 18 * progress ** 2);
    ctx.stroke();
  }
}

function hand(ctx, x, y, phase, opacity) {
  ctx.save();
  const scale = .46 + Math.min(phase * 3, 1) * .54;
  ctx.translate(x, y);
  ctx.rotate(-.3 + phase * .16);
  ctx.scale(scale, scale);
  ctx.beginPath();
  ctx.moveTo(-34, 55);
  ctx.bezierCurveTo(-39, 32, -63, 11, -74, -2);
  ctx.bezierCurveTo(-87, -20, -76, -32, -61, -23);
  ctx.lineTo(-34, -5);
  ctx.lineTo(-53, -70);
  ctx.bezierCurveTo(-59, -91, -41, -97, -33, -79);
  ctx.lineTo(-8, -33);
  ctx.lineTo(-20, -112);
  ctx.bezierCurveTo(-24, -132, -4, -139, 1, -119);
  ctx.lineTo(17, -42);
  ctx.lineTo(18, -104);
  ctx.bezierCurveTo(18, -125, 37, -125, 39, -105);
  ctx.lineTo(41, -38);
  ctx.lineTo(56, -77);
  ctx.bezierCurveTo(62, -94, 78, -87, 74, -70);
  ctx.lineTo(67, -21);
  ctx.bezierCurveTo(65, 13, 47, 43, 41, 57);
  ctx.closePath();
  const fill = ctx.createLinearGradient(0, -130, 0, 62);
  fill.addColorStop(0, "#fff3ac");
  fill.addColorStop(.55, "#ffbd37");
  fill.addColorStop(1, "#bd571a");
  ctx.globalAlpha = opacity * .52;
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.globalAlpha = opacity;
  ctx.lineWidth = 4;
  ctx.strokeStyle = "#fff0a2";
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(-32, 10);
  ctx.quadraticCurveTo(1, -11, 39, 8);
  ctx.moveTo(-14, 34);
  ctx.quadraticCurveTo(3, 8, 28, 3);
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.restore();
}

function ballTrail(ctx, meta, frame, color, intensity) {
  ctx.strokeStyle = color;
  ctx.lineCap = "round";
  for (let index = frame - 14; index < frame; index += 1) {
    const from = meta.ball?.[index];
    const to = meta.ball?.[index + 1];
    if (!from || !to) continue;
    const fade = 1 - (frame - index) / 15;
    ctx.globalAlpha = fade;
    ctx.lineWidth = (2 + fade * 7) * intensity;
    ctx.beginPath();
    ctx.moveTo(...from);
    ctx.lineTo(...to);
    ctx.stroke();
  }
}

export function drawEffects(canvas, meta, events, frame, intensity) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!intensity) return;
  const start = events.find(event => event.type === "PASS_START");
  const end = events.find(event => event.type === "PASS_RECEIVED");
  if (start && frame >= start.frame && frame <= (end?.frame ?? start.frame + meta.fps)) {
    ctx.save();
    ctx.shadowColor = "#ff941e";
    ctx.shadowBlur = 18 * intensity;
    ballTrail(ctx, meta, frame, "#ffae37", intensity);
    ctx.restore();
  }
  for (const event of events) {
    const style = appearances[event.type];
    if (!style || !event.position) continue;
    const time = (frame - event.frame) / meta.fps;
    const anticipation = event.type === "SHOT" ? .25 : event.type === "SAVE" ? .18 : 0;
    if (time < -anticipation || time > style.duration) continue;
    const progress = Math.max(0, time / style.duration);
    const [x, y] = event.position;
    ctx.save();
    ctx.shadowColor = style.color;
    ctx.shadowBlur = 20 * intensity;
    if (event.type === "SAVE") {
      hand(ctx, x, y, (time + anticipation) / (style.duration + anticipation), Math.min(1, intensity * (1 - progress)));
    }
    if (event.type === "SHOT" && time < 0) {
      pulse(ctx, x, y, -time / anticipation, style.color, 80, intensity);
    }
    if (time >= 0) {
      if (event.type === "SHOT") ballTrail(ctx, meta, frame, style.color, intensity);
      pulse(ctx, x, y, progress, style.color, event.type === "GOAL" ? 280 : 145, intensity);
      sparks(ctx, x, y, progress, style.color, event.frame, event.type === "GOAL" ? 2.8 : 1.55, intensity);
      if (event.player) pulse(ctx, ...event.player, progress, style.color, 56, intensity);
      if (event.type === "INTERCEPTION") {
        ctx.globalAlpha = .85 * (1 - progress);
        ctx.strokeStyle = style.color;
        ctx.lineWidth = 5 * intensity;
        ctx.beginPath();
        ctx.moveTo(x - 48, y + 36);
        ctx.lineTo(x - 20, y - 48);
        ctx.lineTo(x + 38, y - 66);
        ctx.lineTo(x + 51, y + 3);
        ctx.closePath();
        ctx.stroke();
      }
      if (event.type === "GOAL") {
        ctx.fillStyle = "#fff0aa";
        ctx.globalAlpha = Math.min(1, 1.7 * (1 - progress));
        ctx.font = 'italic 900 96px Impact, "Arial Narrow", sans-serif';
        ctx.textAlign = "center";
        ctx.fillText("GOL!", canvas.width / 2, canvas.height * .25);
      }
    }
    ctx.restore();
  }
}
