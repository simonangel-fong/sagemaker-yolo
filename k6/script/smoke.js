// Smoke test: one VU, no concurrency. A contract check rather than a load
// test -- is the deployment wired up and returning well-formed detections?
//
// Usage:
//     node k6/script/prepare-images.js
//     k6 run -e BASE_URL=https://yolo.arguswatcher.net k6/script/smoke.js

import { check, fail } from "k6";
import http from "k6/http";
import { Rate, Trend } from "k6/metrics";

import {
  CONF,
  PREDICT_URL,
  READY_URL,
  TIMEOUT,
  checkConfig,
} from "./lib/config.js";
import { imageAt, images } from "./lib/images.js";

const ITERATIONS = Number(__ENV.ITERATIONS || "5");
const detectionRate = new Rate("plate_detected");
const detectionCount = new Trend("detections_per_image");
const predictLatency = new Trend("predict_latency", true);

export const options = {
  scenarios: {
    smoke: {
      executor: "per-vu-iterations",
      vus: 1,
      iterations: ITERATIONS,
      maxDuration: "10m",
    },
  },
  thresholds: {
    http_req_failed: ["rate==0"],
    checks: ["rate==1"],
    // >= not >: at exactly 80% the run should pass, which is what "most
    // images must yield a detection" means. Strict > also makes small runs
    // unpassable -- 4/5 is 0.8 exactly.
    plate_detected: ["rate>=0.8"],
  },
};

export function setup() {
  checkConfig();

  const res = http.get(READY_URL, {
    timeout: TIMEOUT,
    tags: { name: "readiness" },
  });

  if (res.status === 0) {
    fail(
      `cannot reach ${READY_URL} -- ${res.error || "connection failed"}. ` +
        `DNS/TLS/network, not an HTTP error; check BASE_URL resolves.`,
    );
  }

  if (res.status !== 200) {
    fail(
      `readiness returned ${res.status} at ${READY_URL} -- is BASE_URL right?`,
    );
  }

  const body = res.json();
  if (!body || !Array.isArray(body.classes)) {
    fail(`readiness body has no classes array: ${res.body}`);
  }

  console.log(
    `endpoint ready -- model "${body.name}", classes [${body.classes}], ` +
      `imgsz ${body.imgsz}`,
  );
  console.log(
    `corpus of ${images.length} images, conf ${CONF}, ${ITERATIONS} iterations`,
  );

  return { classes: body.classes };
}

export default function (data) {
  const image = imageAt(__ITER);

  const payload = JSON.stringify({
    instances: [{ image: { b64: image.b64 }, conf: CONF }],
  });

  const res = http.post(PREDICT_URL, payload, {
    headers: { "Content-Type": "application/json" },
    timeout: TIMEOUT,
    tags: { name: "predict" },
  });

  predictLatency.add(res.timings.duration);

  const body = tryJson(res);

  const ok = check(
    res,
    {
      "status is 200": (r) => r.status === 200,
    },
    { image: image.name },
  );

  if (!ok) {
    // app.py returns a string "detail" for 400/413/502 naming the problem.
    const detail =
      body && body.detail ? body.detail : String(res.body).slice(0, 200);
    console.error(
      `${image.name} (${image.sha256}) -> ${res.status}: ${detail}`,
    );
    return;
  }

  const shapeOk = check(
    body,
    {
      "body has predictions[0]": (b) =>
        !!b && Array.isArray(b.predictions) && b.predictions.length > 0,
      "count matches detections length": (b) =>
        b.predictions[0].count === b.predictions[0].detections.length,
      "boxes are well formed": (b) =>
        b.predictions[0].detections.every(
          (det) =>
            typeof det.confidence === "number" &&
            typeof det.class_name === "string" &&
            ["x1", "y1", "x2", "y2"].every(
              (k) => typeof det.box[k] === "number",
            ),
        ),
      "confidence respects the conf filter": (b) =>
        b.predictions[0].detections.every((det) => det.confidence >= CONF),
      "class is one the endpoint declared": (b) =>
        b.predictions[0].detections.every((det) =>
          data.classes.includes(det.class_name),
        ),
    },
    { image: image.name },
  );

  if (!shapeOk) {
    console.error(
      `${image.name} (${image.sha256}) -> failed a body check: ${String(res.body).slice(0, 300)}`,
    );
    return;
  }

  const { count } = body.predictions[0];
  detectionCount.add(count);
  detectionRate.add(count > 0);

  if (count === 0) {
    console.warn(
      `${image.name} (${image.sha256}) -> no detections above ${CONF}`,
    );
  }
}

function tryJson(res) {
  try {
    return res.json();
  } catch (err) {
    return null;
  }
}
