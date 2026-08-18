export const BASE_URL = (__ENV.BASE_URL || "").replace(/\/+$/, "");

// Matches the name web/js/main.js uses.
export const MODEL = __ENV.MODEL || "sagemaker-yolo";

export const CONF = Number(__ENV.CONF || "0.25");

export const READY_URL = `${BASE_URL}/v1/models/${MODEL}`;
export const PREDICT_URL = `${BASE_URL}/v1/models/${MODEL}:predict`;

export const TIMEOUT = __ENV.TIMEOUT || "120s";

export function checkConfig() {
  if (!BASE_URL) {
    throw new Error(
      "BASE_URL is required -- the origin serving /v1/*, e.g. "
      + "https://yolo.arguswatcher.net. Pass it with \"k6 run -e BASE_URL=...\" "
      + "or as an environment variable when running under compose.",
    );
  }

  if (!BASE_URL.startsWith("http://") && !BASE_URL.startsWith("https://")) {
    throw new Error(`BASE_URL must include the scheme, got "${BASE_URL}"`);
  }

  if (!Number.isFinite(CONF) || CONF < 0 || CONF > 1) {
    throw new Error(`CONF must be between 0 and 1, got "${__ENV.CONF}"`);
  }
}
