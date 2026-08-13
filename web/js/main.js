// Browser client for the YOLO predictor.
//
// Nginx proxies /v1/ to the inference container, so requests are same-origin
// and no CORS handling is needed on the Python side.

const MODEL = "yolo-car-plate";
const READY_URL = `/v1/models/${MODEL}`;
const PREDICT_URL = `/v1/models/${MODEL}:predict`;

const els = {
  status: document.getElementById("status"),
  file: document.getElementById("file"),
  conf: document.getElementById("conf"),
  confOut: document.getElementById("confOut"),
  detect: document.getElementById("detect"),
  message: document.getElementById("message"),
  canvas: document.getElementById("canvas"),
  results: document.getElementById("results"),
  rows: document.getElementById("rows"),
};

const ctx = els.canvas.getContext("2d");

// The selected image, kept so it can be redrawn when boxes arrive.
let image = null;
let imageB64 = null;

function say(text, isError = false) {
  els.message.textContent = text;
  els.message.classList.toggle("error", isError);
}

// --- model readiness ------------------------------------------------------

async function checkModel() {
  try {
    const res = await fetch(READY_URL);
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || res.statusText);

    els.status.textContent = `ready · ${body.classes.join(", ")} · ${body.imgsz}px`;
    els.status.className = "status ready";
  } catch (err) {
    els.status.textContent = `unavailable — ${err.message}`;
    els.status.className = "status down";
  }
}

// --- image selection ------------------------------------------------------

els.file.addEventListener("change", () => {
  const file = els.file.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = () => {
    // data URL is "data:image/jpeg;base64,XXXX" -- the API wants only the XXXX
    imageB64 = reader.result.split(",")[1];

    image = new Image();
    image.onload = () => {
      draw([]);
      els.detect.disabled = false;
      els.results.hidden = true;
      say(`${file.name} · ${image.naturalWidth}x${image.naturalHeight}`);
    };
    image.src = reader.result;
  };
  reader.readAsDataURL(file);
});

els.conf.addEventListener("input", () => {
  els.confOut.textContent = Number(els.conf.value).toFixed(2);
});

// --- drawing --------------------------------------------------------------

function draw(detections) {
  // Canvas matches the image's natural size, because the API returns boxes in
  // original-image pixels. CSS scales the canvas down for display; the box
  // coordinates stay correct because they scale with it.
  els.canvas.width = image.naturalWidth;
  els.canvas.height = image.naturalHeight;
  els.canvas.classList.add("loaded");

  ctx.drawImage(image, 0, 0);

  // Scale line and text with the image so they stay legible on large photos.
  const unit = Math.max(2, Math.round(image.naturalWidth / 400));
  ctx.lineWidth = unit;
  ctx.font = `600 ${unit * 7}px ui-sans-serif, system-ui, sans-serif`;
  ctx.textBaseline = "bottom";

  for (const det of detections) {
    const { x1, y1, x2, y2 } = det.box;
    const label = `${det.class_name} ${det.confidence.toFixed(2)}`;

    ctx.strokeStyle = "#f85149";
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

    // Label sits above the box, or inside it when the box touches the top edge.
    const padding = unit * 2;
    const textWidth = ctx.measureText(label).width;
    const textHeight = unit * 9;
    const labelY = y1 - padding > textHeight ? y1 - padding : y1 + textHeight;

    ctx.fillStyle = "#f85149";
    ctx.fillRect(x1 - unit / 2, labelY - textHeight,
      textWidth + padding * 2, textHeight);

    ctx.fillStyle = "#ffffff";
    ctx.fillText(label, x1 + padding - unit / 2, labelY - unit);
  }
}

function tabulate(detections) {
  els.rows.replaceChildren();

  for (const [i, det] of detections.entries()) {
    const { x1, y1, x2, y2 } = det.box;
    const row = document.createElement("tr");
    for (const value of [
      i + 1,
      det.class_name,
      det.confidence.toFixed(4),
      `${x1}, ${y1}, ${x2}, ${y2}`,
    ]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    els.rows.append(row);
  }
  els.results.hidden = detections.length === 0;
}

// --- predict --------------------------------------------------------------

els.detect.addEventListener("click", async () => {
  if (!imageB64) return;

  els.detect.disabled = true;
  say("detecting…");
  const started = performance.now();

  try {
    const res = await fetch(PREDICT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instances: [{
          image: { b64: imageB64 },
          conf: Number(els.conf.value),
        }],
      }),
    });

    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || res.statusText);

    const { detections, count } = body.predictions[0];
    const elapsed = Math.round(performance.now() - started);

    draw(detections);
    tabulate(detections);
    say(count === 0
      ? `no detections above ${Number(els.conf.value).toFixed(2)} · ${elapsed} ms`
      : `${count} detection${count > 1 ? "s" : ""} · ${elapsed} ms`);

  } catch (err) {
    say(err.message, true);
  } finally {
    els.detect.disabled = false;
  }
});

checkModel();
