// Readiness probe every scenario runs in setup(). If the endpoint is not
// reachable, one clear failure beats every iteration failing identically.

import { fail } from "k6";
import http from "k6/http";

import { READY_URL, TIMEOUT, checkConfig } from "./config.js";

// Returns the declared class names, which the body checks validate against.
export function waitForEndpoint() {
  checkConfig();

  const res = http.get(READY_URL, {
    timeout: TIMEOUT,
    tags: { name: "readiness" },
  });

  // k6 reports transport failures (DNS, TLS, refused) as status 0, not as an
  // HTTP status -- without this a dead hostname reads as a server error.
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

  return body.classes;
}
