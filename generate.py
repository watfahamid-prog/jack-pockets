from __future__ import annotations
import argparse,json,re,subprocess
from pathlib import Path
from llm import generate
from tts import synthesize
from assets import search_pexels,search_pexels_videos,make_asset_plan,generate_role_asset
from research import search_web
from manifest import build
from quality import validate
PROFILES={"youtube":{"width":1920,"height":1080,"fps":60}}
def slug(s:str)->str:return re.sub(r"[^a-z0-9]+","-",s.lower()).strip("-")[:55] or "run"
def main():
 p=argparse.ArgumentParser(description="Generate an editorially planned documentary video.")
 p.add_argument("--topic",required=True);p.add_argument("--profile",choices=PROFILES,default="youtube");p.add_argument("--no-render",action="store_true");p.add_argument("--assets-per-beat",type=int,default=2);a=p.parse_args()
 root=Path("public/runs")/slug(a.topic);root.mkdir(parents=True,exist_ok=True)
 plan=generate(a.topic);plan["topic"]=a.topic
 research=[]
 for b in plan.get("beats",[]):
  q=f"{a.topic}: {b.get('title','')} {b.get('narration','')[:500]}"
  found=search_web(q,limit=3)
  b["research"]=found
  research.extend(found)
 plan["sources"]=list(dict.fromkeys(x["url"] for x in research if x.get("url")))
 (root/"research.json").write_text(json.dumps(research,indent=2),encoding="utf-8")
 (root/"plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
 narration=" ".join(str(b.get("narration","")) for b in plan.get("beats",[]));audio=root/"narration.mp3";synthesize(narration,audio)
 subprocess.run(["python","scripts/audio_aligner.py",str(audio),"--out",str(root/"alignment.json")],check=True)
 words=json.loads((root/"alignment.json").read_text());asset_sets=[]
 for i,b in enumerate(plan.get("beats",[])):
  # Stock footage must come first: build_shots selects assets by index, so generated
  # cards placed first can otherwise crowd out every downloaded video in short beats.
  stock_assets=[]
  generated_assets=[]
  editorial=b.get("editorial") or {}
  narration=str(b.get("narration",""))
  photo_queries=list(dict.fromkeys((b.get("keywords") or [a.topic]) + [narration[:160]]))
  for q in photo_queries[:max(1,a.assets_per_beat)]:
   try:
    videos=search_pexels_videos(str(q),root/f"assets-{i}",limit=1)
    if videos:
     for item in videos:
      item["src"]=str(Path(item["src"]).relative_to("public")).replace("\\","/")
      stock_assets.append(item)
     continue
    print(f"[pexels] no video result for query={str(q)[:80]!r}; trying photos")
   except Exception as e:
    print(f"[pexels] video search failed: {e}; trying photo fallback")
   try:
    photos=search_pexels(str(q),root/f"assets-{i}",limit=1)
    for item in photos:
     item["src"]=str(Path(item["src"]).relative_to("public")).replace("\\","/")
     stock_assets.append(item)
   except Exception as e:
    print(f"[pexels] photo search failed: {e}")
  roles=make_asset_plan(narration,editorial)
  generated_dir=root/"generated"
  for j,r in enumerate(roles):
   item=generate_role_asset(r["role"],narration,generated_dir,research,i*10+j)
   if item:
    item["src"]=str(Path(item["src"]).relative_to("public")).replace("\\","/")
    generated_assets.append(item)
  aset=stock_assets+generated_assets
  print(f"[assets] beat={i+1} stock_video={sum(x.get('kind')=='video' for x in stock_assets)} stock_photo={sum(x.get('kind')=='photo' for x in stock_assets)} generated={len(generated_assets)}")
  asset_sets.append(aset)
 manifest=build(plan,str(audio.relative_to("public")).replace("\\","/"),words,asset_sets,PROFILES[a.profile],root/"manifest.json")
 errors=validate(str(manifest))
 if errors:raise SystemExit("QUALITY GATE FAILED:\n"+"\n".join(errors))
 print(f"READY: {manifest}")
 if not a.no_render:
  out=Path("out")/f"{slug(a.topic)}.mp4"
  subprocess.run(["npx","remotion","render","src/index.tsx","JackPocketsVideo",str(out),"--props",str(manifest),"--codec=h264","--audio-codec=aac","--pixel-format=yuv420p","--crf=18","--enforce-audio-track"],check=True)
  probe=subprocess.run(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(out)],capture_output=True,text=True,check=True)
  info=json.loads(probe.stdout);streams=info.get("streams",[])
  video=next((s for s in streams if s.get("codec_type")=="video"),None)
  audio=next((s for s in streams if s.get("codec_type")=="audio"),None)
  if not video or not audio:raise SystemExit("FINAL QC FAILED: missing video or audio stream")
  if video.get("width")!=1920 or video.get("height")!=1080:raise SystemExit("FINAL QC FAILED: output is not 1920x1080")
  if video.get("r_frame_rate")!="60/1":raise SystemExit("FINAL QC FAILED: output is not 60 FPS")
  duration=float(info.get("format",{}).get("duration",0))
  if duration<480 or duration>1800:raise SystemExit(f"FINAL QC FAILED: duration {duration:.2f}s outside 8-30 minute range")
  print(f"FINAL QC PASSED: {out} | {duration:.2f}s | 1920x1080 | 60fps | audio=yes")

if __name__=="__main__":main()