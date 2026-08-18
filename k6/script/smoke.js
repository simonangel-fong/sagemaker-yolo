// Smoke test: RATE requests per second for DURATION, checking that every
// response is a well-formed detection. A contract check, not a stress test.
//
// Usage:
//     node k6/script/prepare-images.js
//     k6 run -e BASE_URL=https://yolo.arguswatcher.net k6/script/smoke.js

import exec from "k6/execution";
import { Rate, Trend } from "k6/metrics";

import { CONF } from "./lib/config.js";
import { imageAt, images } from "./lib/images.js";
import { predictOnce } from "./lib/predict.js";
import { waitForEndpoint } from "./lib/ready.js";

const RATE = Number(__ENV.RATE || "1");
const DURATION = __ENV.DURATION || "1m";

const detectionRate = new Rate("plate_detected");
const detectionCount = new Trend("detections_per_image");

export const options = {
  scenarios: {
    smoke: {
      // Arrival-rate, not per-VU-iterations: pins the request rate however
      // slow the endpoint is, instead of stretching the run.
      executor: "constant-arrival-rate",
      rate: RATE,
      timeUnit: "1s",
      duration: DURATION,
      // Headroom so a ~10s cold start cannot starve the arrival rate.
      preAllocatedVUs: Math.max(5, RATE * 12),
      maxVUs: Math.max(10, RATE * 25),
    },
  },
  thresholds: {
    http_req_failed: ["rate==0"],
    checks: ["rate==1"],
    // >= not >: strict > fails at exactly 80%, making small runs unpassable.
    plate_detected: ["rate>=0.8"],
  },
};

export function setup() {
  const classes = waitForEndpoint();

  console.log(
    `corpus of ${images.length} images, conf ${CONF}, ` +
      `${RATE} req/s for ${DURATION}`,
  );

  return { classes };
}

export default function (data) {
  // Test-wide counter, not __ITER: __ITER is per-VU, so several VUs would each
  // start at 0 and send the same image.
  const image = imageAt(exec.scenario.iterationInTest);

  const count = predictOnce(image, data.classes);
  if (count === null) return;

  detectionCount.add(count);
  detectionRate.add(count > 0);

  if (count === 0) {
    console.warn(
      `${image.name} (${image.sha256}) -> no detections above ${CONF}`,
    );
  }
}
