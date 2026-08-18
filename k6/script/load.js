// Load test: step the arrival rate from 1 req/s up to MAX, holding each step
// long enough to see whether latency is stable there or still climbing.
//
// The endpoint is serverless with MaxConcurrency=5, so the interesting result
// is the step where latency starts climbing -- past that, requests queue
// behind the concurrency limit rather than being served faster.
//
// Usage:
//     node k6/script/prepare-images.js
//     docker compose -f k6/docker-compose.yml run --rm k6 load.js
//     MAX=40 STEPS=8 docker compose -f k6/docker-compose.yml run --rm k6 load.js

import { Rate, Trend } from "k6/metrics";
import exec from "k6/execution";

import { CONF } from "./lib/config.js";
import { imageAt, images } from "./lib/images.js";
import { predictOnce } from "./lib/predict.js";
import { waitForEndpoint } from "./lib/ready.js";

const MAX = Number(__ENV.MAX || "20");
const STEPS = Number(__ENV.STEPS || "5");
const STEP_DURATION = __ENV.STEP_DURATION || "30s";
const RAMP = __ENV.RAMP || "10s";

if (!Number.isFinite(MAX) || MAX < 1) {
  throw new Error(`MAX must be a positive number, got "${__ENV.MAX}"`);
}
if (!Number.isInteger(STEPS) || STEPS < 1) {
  throw new Error(`STEPS must be a positive integer, got "${__ENV.STEPS}"`);
}

const detectionRate = new Rate("plate_detected");
const detectionCount = new Trend("detections_per_image");

// Evenly spaced targets from 1 to MAX. Each step ramps over RAMP then holds for
// STEP_DURATION, so the held section is what the percentiles describe -- a
// pure ramp would blur every rate together in one bucket.
function buildStages() {
  const stages = [];
  for (let i = 1; i <= STEPS; i += 1) {
    const target = Math.max(1, Math.round((MAX * i) / STEPS));
    stages.push({ target, duration: RAMP });
    stages.push({ target, duration: STEP_DURATION });
  }
  // Wind down rather than cutting off, so in-flight requests finish and are
  // not counted as failures.
  stages.push({ target: 0, duration: RAMP });
  return stages;
}

const stages = buildStages();

export const options = {
  scenarios: {
    load: {
      executor: "ramping-arrival-rate",
      startRate: 1,
      timeUnit: "1s",
      stages,
      // Sized for the peak: at MAX req/s with responses up to ~10s under
      // saturation, k6 needs enough VUs to keep starting new requests.
      preAllocatedVUs: Math.max(10, MAX * 3),
      maxVUs: Math.max(20, MAX * 10),
    },
  },
  thresholds: {
    // A load test exists to find the knee, so these are an error budget
    // rather than the zero-tolerance gates smoke.js uses.
    http_req_failed: ["rate<0.01"],
    checks: ["rate>0.95"],
    predict_latency: ["p(95)<5000"],
    plate_detected: ["rate>=0.8"],
  },
};

export function setup() {
  const classes = waitForEndpoint();

  const targets = stages
    .filter((s) => s.duration === STEP_DURATION)
    .map((s) => s.target);

  console.log(
    `corpus of ${images.length} images, conf ${CONF} -- stepping ` +
      `${targets.join(" -> ")} req/s, ${STEP_DURATION} at each`,
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
}
