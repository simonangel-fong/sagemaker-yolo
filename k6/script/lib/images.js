import { SharedArray } from "k6/data";

// Relative to k6/script/lib/, resolving to k6/data/ locally and in the
// container alike.
const DEFAULT_CORPUS = "../../data/corpus.json";
const CORPUS_PATH = __ENV.CORPUS || DEFAULT_CORPUS;

// SharedArray, not a plain array: every VU would otherwise hold its own copy
// of the whole base64 corpus.
export const images = new SharedArray("images", function () {
  let raw;
  try {
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
