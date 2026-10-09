import React from "react";
import { AbsoluteFill, Audio, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { VideoManifest, Beat, Shot, Layer } from "./types";

const src = (value: string) => value.startsWith("http") ? value : staticFile(value);
const textShadow = "0 3px 18px rgba(0,0,0,.95)";
const clamp = (value: number, min = 0, max = 1) => Math.max(min, Math.min(max, value));
const ease = (value: number) => value * value * (3 - 2 * value);

const LayerView: React.FC<{ layer: Layer; beat: Beat; shot: Shot; frame: number; fps: number }> = ({ layer, beat, shot, frame, fps }) => {
  const local = Math.max(0, frame / fps - (beat.start + shot.start));
  const duration = Math.max(0.01, shot.end - shot.start);
  const reveal = ease(clamp(local / 0.22));
  const scale = layer.animation === "push"
    ? interpolate(local, [0, duration], [1.10, 1.015], { extrapolateRight: "clamp" })
    : layer.animation === "pull"
      ? interpolate(local, [0, duration], [1.015, 1.08], { extrapolateRight: "clamp" })
      : 1;
  const panX = layer.animation === "pan" ? interpolate(local, [0, duration], [-2, 2], { extrapolateRight: "clamp" }) : 0;
  const panY = layer.animation === "parallax" ? interpolate(local, [0, duration], [1.5, -1.5], { extrapolateRight: "clamp" }) : 0;
  const base: React.CSSProperties = {
    position: "absolute", left: `${layer.x}%`, top: `${layer.y}%`,
    width: `${layer.width}%`, height: `${layer.height}%`, opacity: (layer.opacity ?? 1) * reveal,
    zIndex: layer.z, transform: `translate(${panX}%,${panY}%) rotate(${layer.rotation}deg) scale(${scale})`,
    transformOrigin: "center center",
  };

  if (layer.kind === "image" && layer.assetId) {
    const asset = beat.assets.find(item => item.id === layer.assetId);
    if (!asset) return null;
    const media = asset.kind === "video"
      ? <OffthreadVideo src={src(asset.src)} muted startFrom={0} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
      : <Img src={src(asset.src)} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />;
    return <div style={{ ...base, overflow: "hidden", background: "#111" }}>
      {media}
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg,rgba(0,0,0,.03),transparent 58%,rgba(0,0,0,.42))" }} />
    </div>;
  }
  if (layer.kind === "highlight") return <div style={{ ...base, background: "linear-gradient(90deg,rgba(245,205,40,.4),rgba(245,205,40,.04))", mixBlendMode: "screen" }} />;
  if (layer.kind === "arrow") return <div style={{ ...base, color: "#fff", fontSize: "4vw", fontWeight: 900, textShadow }}>{layer.text || "→"}</div>;
  if (layer.kind === "label") return <div style={{ ...base, boxSizing: "border-box", background: "rgba(8,8,8,.68)", border: "1px solid rgba(255,255,255,.22)", borderRadius: 5, padding: "7px 11px", fontFamily: "Arial,sans-serif", fontWeight: 700, fontSize: "1vw", letterSpacing: 1.2, color: "#fff" }}>{layer.text}</div>;
  if (layer.kind === "text") return <div style={{ ...base, fontFamily: "Arial Black,Arial,sans-serif", fontWeight: 900, fontSize: "clamp(34px,5vw,96px)", lineHeight: 0.9, letterSpacing: -2, color: "#f5f2ea", textTransform: "uppercase", textShadow, display: "flex", alignItems: "flex-end" }}>{layer.text}</div>;
  return null;
};

const ShotView: React.FC<{ beat: Beat; shot: Shot; frame: number; fps: number }> = ({ beat, shot, frame, fps }) => {
  const local = frame / fps - (beat.start + shot.start);
  const duration = Math.max(0.01, shot.end - shot.start);
  const flash = shot.actions.find(action => action.type === "flash");
  const zoom = shot.actions.find(action => action.type === "zoom");
  const shake = shot.actions.find(action => action.type === "shake");
  const scale = zoom ? 1 + zoom.intensity * 0.08 * clamp(local / Math.max(0.01, zoom.duration)) : 1;
  const dx = shake ? Math.sin(local * 45) * shake.intensity * 4 : 0;
  const flashOpacity = flash ? interpolate(local, [flash.at * duration, flash.at * duration + flash.duration], [0.12, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0;

  return <AbsoluteFill style={{ overflow: "hidden", background: "#080808", transform: `translateX(${dx}px) scale(${scale})` }}>
    {shot.layers.map(layer => <LayerView key={layer.id} layer={layer} beat={beat} shot={shot} frame={frame} fps={fps} />)}
    {flashOpacity > 0 && <AbsoluteFill style={{ background: "#fff", opacity: flashOpacity, zIndex: 30 }} />}
    <AbsoluteFill style={{ pointerEvents: "none", boxShadow: "inset 0 0 160px rgba(0,0,0,.36)", zIndex: 32 }} />
    <AbsoluteFill style={{ pointerEvents: "none", background: "linear-gradient(180deg,rgba(0,0,0,.2),transparent 22%,transparent 78%,rgba(0,0,0,.28))", zIndex: 33 }} />
  </AbsoluteFill>;
};

const captionAt = (words: Array<{ word: string; start: number; end: number }>, time: number) =>
  words.find(word => time >= word.start && time < word.end)?.word || "";

export const JackPocketsVideo: React.FC<{ manifest: VideoManifest }> = ({ manifest }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const time = frame / fps;
  const activeBeat = manifest.beats.find(beat => time >= beat.start && time < beat.end);
  const activeShot = activeBeat?.shots.find(shot => time >= activeBeat.start + shot.start && time < activeBeat.start + shot.end);
  const caption = captionAt(manifest.captions, time);

  return <AbsoluteFill style={{ background: "#101010", overflow: "hidden" }}>
    {activeBeat && activeShot
      ? <ShotView beat={activeBeat} shot={activeShot} frame={frame} fps={fps} />
      : <AbsoluteFill style={{ background: "#080808" }} />}
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 80 }}>
      {activeBeat && <div style={{ position: "absolute", left: "5.5%", top: "4.5%", fontFamily: "Arial,sans-serif", fontSize: 15, fontWeight: 700, letterSpacing: 2.2, color: "rgba(255,255,255,.72)", textTransform: "uppercase", textShadow }}>{String(activeBeat.kind).replace(/-/g, " ")}</div>}
      {caption && <div style={{ position: "absolute", left: "12%", right: "12%", bottom: "6%", minHeight: 52, display: "flex", alignItems: "center", justifyContent: "center", padding: "8px 18px", boxSizing: "border-box", background: "rgba(0,0,0,.32)", fontFamily: "Arial,sans-serif", fontSize: "clamp(22px,2.15vw,40px)", fontWeight: 800, color: "#fff", textShadow: "0 2px 12px #000", textAlign: "center" }}>{caption}</div>}
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 3, background: "rgba(255,255,255,.16)" }}>
        <div style={{ height: "100%", width: `${Math.min(100, time / manifest.duration * 100)}%`, background: "#e8c547" }} />
      </div>
    </AbsoluteFill>
    {manifest.audioSrc && <Audio src={staticFile(manifest.audioSrc)} />}
    {manifest.musicSrc && <Audio src={staticFile(manifest.musicSrc)} volume={0.12} />}
    {activeBeat && activeShot && activeShot.sfx?.map((cue, index) => cue.src ? <Audio key={`sfx-${activeShot.id}-${index}`} src={staticFile(cue.src)} startFrom={0} volume={cue.gain} /> : null)}
  </AbsoluteFill>;
};
