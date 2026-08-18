// Build the base64 corpus the k6 scripts read.
// Usage:
//     node k6/script/prepare-images.js [--count N] [--out PATH] [--src DIR]
//
// SRC/OUT/COUNT are honoured as environment variables too, so the container
// can be pointed at its mounts without baking paths into the entrypoint.
// Precedence: flag > env var > location-relative default.

import { createHash } from "node:crypto";
import {
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const K6 = resolve(HERE, "..");
const REPO = resolve(HERE, "..", "..");

// Location-relative defaults, used when neither a flag nor an env var is set.
// Corpus lives in k6/data/, not k6/script/ -- generated data stays out of the
// source tree.
const DEFAULT_SRC = process.env.SRC || join(REPO, "data", "raw");
const DEFAULT_OUT = process.env.OUT || join(K6, "data", "corpus.json");

// data/raw holds a .txt label file beside every image; those are not payloads.
const IMAGE_EXTENSIONS = new Set([".jpg", ".jpeg", ".png"]);

// Serverless SageMaker caps the InvokeEndpoint payload at 4 MB, and app.py
// rejects anything larger with a 413. Keep this in step with MAX_BODY_BYTES
// there -- a load test that bakes in guaranteed failures measures nothing.
const MAX_B64_BYTES = 4 * 1024 * 1024;

// All 556 images would be several hundred MB of base64 held in memory by k6.
const DEFAULT_COUNT = 30;

function parseCount(value, label) {
  if (value === undefined || value === "") return undefined;

  const n = Number(value);
  if (!Number.isInteger(n) || n < 1) {
    throw new Error(`${label} must be a positive integer, got "${value}"`);
  }
  return n;
}

function parseArgs(argv) {
  // Env vars are read here rather than at module scope so a bad value surfaces
  // through main()'s error handler instead of as an unhandled throw.
  const args = {
    count: parseCount(process.env.COUNT, "COUNT") ?? DEFAULT_COUNT,
    out: DEFAULT_OUT,
    src: DEFAULT_SRC,
  };

  for (let i = 0; i < argv.length; i += 2) {
    const flag = argv[i];
    const value = argv[i + 1];

    if (value === undefined) throw new Error(`${flag} needs a value`);

    if (flag === "--count") {
      args.count = parseCount(value, "--count");
    } else if (flag === "--out") {
      args.out = resolve(value);
    } else if (flag === "--src") {
      args.src = resolve(value);
    } else {
      throw new Error(`unknown flag "${flag}"`);
    }
  }

  return args;
}

// Even spread across the size range, so the sample keeps payload variety.
function sampleEvenly(items, count) {
  if (count >= items.length) return items;

  const step = (items.length - 1) / (count - 1);
  return Array.from({ length: count }, (_, i) => items[Math.round(i * step)]);
}

function main() {
  const { count, out, src } = parseArgs(process.argv.slice(2));

  let entries;
  try {
    entries = readdirSync(src);
  } catch (err) {
    // data/raw is gitignored, so a fresh clone will not have it.
    throw new Error(
      `cannot read ${src} -- data/raw is gitignored and may not exist in this ` +
        `clone. Point --src at the images, or restore data/raw.`,
    );
  }

  const images = entries
    .filter((name) => IMAGE_EXTENSIONS.has(extname(name).toLowerCase()))
    .map((name) => {
      const path = join(src, name);
      return { name, path, bytes: statSync(path).size };
    })
    .sort((a, b) => a.bytes - b.bytes);

  if (images.length === 0) {
    throw new Error(`no .jpg/.jpeg/.png files in ${src}`);
  }

  // base64 inflates by 4/3, so cap the raw file size at 3/4 of the b64 limit.
  const maxFileBytes = Math.floor((MAX_B64_BYTES / 4) * 3);
  const withinCap = images.filter((img) => img.bytes <= maxFileBytes);
  const skipped = images.length - withinCap.length;

  if (withinCap.length === 0) {
    throw new Error(
      `every image in ${src} is over the ${MAX_B64_BYTES / 1024 / 1024} MB ` +
        `base64 cap -- nothing to test with`,
    );
  }

  const selected = sampleEvenly(withinCap, count);

  const corpus = selected.map((img) => {
    const raw = readFileSync(img.path);
    return {
      name: img.name,
      bytes: img.bytes,
      sha256: createHash("sha256").update(raw).digest("hex").slice(0, 12),
      b64: raw.toString("base64"),
    };
  });

  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, JSON.stringify(corpus));

  const totalB64 = corpus.reduce((sum, img) => sum + img.b64.length, 0);
  const mb = (n) => (n / 1024 / 1024).toFixed(1);

  console.log(`source        ${src}`);
  console.log(`images found  ${images.length}`);
  if (skipped > 0) {
    console.log(
      `skipped       ${skipped} over the ${mb(MAX_B64_BYTES)} MB base64 cap`,
    );
  }
  console.log(`selected      ${corpus.length}`);
  console.log(
    `size range    ${mb(selected[0].bytes)} MB - ${mb(selected[selected.length - 1].bytes)} MB`,
  );
  console.log(`corpus        ${out}  (${mb(totalB64)} MB base64)`);
}

try {
  main();
} catch (err) {
  console.error(`prepare-images: ${err.message}`);
  process.exit(1);
}
