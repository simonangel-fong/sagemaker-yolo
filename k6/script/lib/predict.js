// One predict request plus the checks every scenario runs on the response.
// Shared so smoke.js and load.js cannot drift apart on what "correct" means.

import { check } from "k6";
import http from "k6/http";
import { Trend } from "k6/metrics";

import { CONF, PREDICT_URL, TIMEOUT } from "./config.js";

export const predictLatency = new Trend("predict_latency", true);

// Returns the detection count, or null when the request or its body failed a
// check -- the caller decides whether that is fatal for its scenario.
export function predictOnce(image, classes) {
  const payload = JSON.stringify({
    instances: [{ image: { b64: image.b64 }, conf: CONF }],
  });

  const res = http.post(PREDICT_URL, payload, {
    headers: { "Content-Type": "application/json" },
    timeout: TIMEOUT,
    // Without an explicit tag k6 groups by URL, and every request shares one.
    tags: { name: "predict" },
  });

  predictLatency.add(res.timings.duration);

  // A CloudFront error comes back as HTML; res.json() would throw a parse
  // error that hides the real failure.
  const body = tryJson(res);

  const ok = check(
    res,
    { "status is 200": (r) => r.status === 200 },
    { image: image.name },
  );

  if (!ok) {
    // app.py returns a string "detail" for 400/413/502 naming the problem.
    const detail =
      body && body.detail ? body.detail : String(res.body).slice(0, 200);
    console.error(`${image.name} (${image.sha256}) -> ${res.status}: ${detail}`);
    return null;
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
          classes.includes(det.class_name),
        ),
    },
    { image: image.name },
  );

  if (!shapeOk) {
    console.error(
      `${image.name} (${image.sha256}) -> failed a body check: ` +
        String(res.body).slice(0, 300),
    );
    return null;
  }

  return body.predictions[0].count;
}

function tryJson(res) {
  try {
    return res.json();
  } catch (err) {
    return null;
  }
}
