import assert from "node:assert/strict";
import test from "node:test";
import { captionAt } from "../caption-utils.js";

test("caption remains visible between adjacent words with a short Whisper gap", () => {
  const words = [
    { word: "This", start: 0, end: 0.20 },
    { word: "works.", start: 0.30, end: 0.50 },
  ];
  assert.equal(captionAt(words, 0.25), "This works.");
});

test("caption is absent during a genuine long pause", () => {
  const words = [
    { word: "Wait.", start: 0, end: 0.20 },
    { word: "Continue", start: 1.0, end: 1.30 },
    { word: "now.", start: 1.35, end: 1.55 },
  ];
  assert.equal(captionAt(words, 0.55), "");
});

test("caption phrase updates at the next sentence without carrying prior sentence text", () => {
  const words = [
    { word: "Hello.", start: 0, end: 0.20 },
    { word: "Next", start: 0.30, end: 0.45 },
    { word: "sentence.", start: 0.50, end: 0.75 },
  ];
  assert.equal(captionAt(words, 0.25), "Hello.");
  assert.equal(captionAt(words, 0.40), "Next sentence.");
});

test("empty word lists return no caption", () => {
  assert.equal(captionAt([], 0.2), "");
});
