export type CaptionWord = { word: string; start: number; end: number };
export declare const CAPTION_GAP_TOLERANCE_SECONDS: number;
export declare function captionAt(words: CaptionWord[], time: number): string;
