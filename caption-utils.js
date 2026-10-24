export const CAPTION_GAP_TOLERANCE_SECONDS = 0.22;

/**
 * Return the current short caption phrase. Word timestamps often leave tiny gaps
 * between adjacent words; keep the same phrase visible across those natural gaps.
 */
export function captionAt(words, time) {
  if (!Array.isArray(words) || words.length === 0 || !Number.isFinite(time)) return "";

  let index = words.findIndex(word => time >= word.start && time < word.end);
  if (index < 0) {
    for (let i = 0; i < words.length - 1; i++) {
      const current = words[i];
      const next = words[i + 1];
      const gap = next.start - current.end;
      if (
        gap >= 0 &&
        gap <= CAPTION_GAP_TOLERANCE_SECONDS &&
        time >= current.end &&
        time < next.start
      ) {
        index = i;
        break;
      }
    }
  }
  if (index < 0) return "";

  const endsSentence = word => /[.!?]["')\]]?$/.test(String(word).trim());
  let start = index;
  while (start > 0 && index - start < 6 && !endsSentence(words[start - 1].word)) start--;

  let end = Math.min(words.length, start + 7);
  for (let i = start; i < end; i++) {
    if (i >= index && endsSentence(words[i].word)) {
      end = i + 1;
      break;
    }
  }
  if (index >= end) {
    start = Math.max(0, index - 3);
    end = Math.min(words.length, start + 7);
  }
  return words.slice(start, end).map(item => String(item.word).trim()).filter(Boolean).join(" ");
}
