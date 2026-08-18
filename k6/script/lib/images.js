import { SharedArray } from "k6/data";

// Relative to k6/script/lib/, so this resolves to k6/data/ both locally and
// under the container mount.
const DEFAULT_CORPUS = "../../data/corpus.json";
const CORPUS_PATH = __ENV.CORPUS || DEFAULT_CORPUS;

export const images = new SharedArray("images", function () {
  let raw;
  try {
    // open() is init-context only, which is exactly where SharedArray runs.
    raw = open(CORPUS_PATH);
  } catch (err) {
    throw new Error(
      `cannot read the corpus (${CORPUS_PATH}, relative to k6/script/lib) -- run `
      + `"node k6/script/prepare-images.js" first, or set CORPUS to an absolute path`,
    );
  }

  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed) || parsed.length === 0) {
    throw new Error(`${CORPUS_PATH} is empty -- re-run prepare-images.js`);
  }

  return parsed;
});

export function imageAt(index) {
  return images[index % images.length];
}
