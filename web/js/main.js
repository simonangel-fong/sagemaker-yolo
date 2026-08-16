// Browser client for the YOLO predictor.
//
// CloudFront routes /v1/* to the Lambda proxy in front of the SageMaker
// endpoint, so requests are same-origin and CORS never applies.

const MODEL = "sagemaker-yolo";
const READY_URL = `/v1/models/${MODEL}`;
const PREDICT_URL = `/v1/models/${MODEL}:predict`;

// The endpoint caps a request at 6 MB of base64, which is ~4.5 MB of file.
// Catching it here gives a clearer message than a 413 from the proxy.
const MAX_FILE_BYTES = 4.5 * 1024 * 1024;

const els = {
  status: document.getElementById("status"),
  file: document.getElementById("file"),
  conf: document.getElementById("conf"),
  confOut: document.getElementById("confOut"),
  detect: document.getElementById("detectBtn"),
  message: document.getElementById("message"),
  stage: document.getElementById("stage"),
  placeholder: document.getElementById("placeholder"),
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
    // Off CloudFront (a plain file server, say) /v1/ isn't proxied anywhere and
    // the 404 page comes back as HTML, so res.json() would throw a parse error
    // that means nothing to a reader. Report the status instead.
    if (!res.ok) throw new Error(`endpoint returned ${res.status}`);

    const body = await res.json();
    els.status.textContent = `ready · ${body.classes.join(", ")} · ${body.imgsz}px`;
    els.status.className = "status-badge ready";
  } catch (err) {
    els.status.textContent = `unavailable — ${err.message}`;
    els.status.className = "status-badge down";
  }
}

// --- image selection ------------------------------------------------------

els.file.addEventListener("change", () => {
  const file = els.file.files[0];
  if (!file) return;

  if (file.size > MAX_FILE_BYTES) {
    els.detect.disabled = true;
    say(`${file.name} is ${(file.size / 1024 / 1024).toFixed(1)} MB — resize below `
      + `${(MAX_FILE_BYTES / 1024 / 1024).toFixed(1)} MB before sending`, true);
    return;
  }

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
  els.stage.classList.add("loaded");
  els.placeholder.hidden = true;

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

    // An error from CloudFront or the proxy may not be JSON, so read the body
    // defensively -- .detail when it parses, the status code when it doesn't.
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error(body?.detail || `request failed (${res.status})`);
    }

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
