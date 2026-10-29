from __future__ import annotations
import json,re
from pathlib import Path
from editorial_brain import build_shots
from gemini_editor import refine_beat

def norm(s: str) -> list[str]:
    # Keep internal apostrophes inside contractions, then normalize them away so
    # text tokens such as "don't" match a Whisper token like "don't" or "dont".
    tokens = re.findall(r"[a-z0-9]+(?:['’][a-z0-9]+)*", str(s).lower())
    return [re.sub(r"[^a-z0-9]", "", token) for token in tokens]

def match_span(text:str,words:list[dict],start:int)->tuple[int,int]:
    target=norm(text)
    flat=[re.sub(r"[^a-z0-9]","",str(w.get("word","")).lower()) for w in words]
    for i in range(start,max(start,len(flat)-len(target)+1)):
        if flat[i:i+len(target)]==target:return i,i+len(target)
    return start,min(len(words),start+len(target))

def build(plan,audio_src,words,assets_by_beat,profile,out):
    beats=[];search_pos=0;global_words=[w for w in words if w.get("word")]
    for i,b in enumerate(plan["beats"]):
        narration=str(b.get("narration",""))
        sentences=[x.strip() for x in re.split(r"(?<=[.!?])\s+",narration) if x.strip()]
        start_i,end_i=match_span(narration,global_words,search_pos)
        if end_i<=start_i: raise ValueError(f"Whisper alignment could not map beat {i+1}.")
        beat=dict(b);beat["id"]=beat.get("id",f"beat-{i+1}")
        # Keep beat starts aligned to the actual spoken words. Leading silence
        # is covered by the first shot; inter-beat silence is covered by holding
        # the previous beat's last shot instead of shifting the next beat early.
        beat["start"] = 0.0 if not beats else round(float(global_words[start_i]["start"]), 3)
        beat["end"] = round(max(beat["start"] + .5, float(global_words[end_i - 1]["end"])), 3)
        beat["assets"]=assets_by_beat[i] if i<len(assets_by_beat) else []
        beat["actions"]=beat.get("actions",[]);beat["sfx"]=beat.get("sfx",[])
        beat=refine_beat(beat)
        beat=build_shots(beat,aligned_words=global_words[start_i:end_i],sentences_override=sentences)
        beats.append(beat);search_pos=max(search_pos,end_i)

    # A visual should remain on screen through pauses between narration beats,
    # rather than leaving the Remotion root with no active beat (black frame).
    if beats and beats[0].get("shots"):
        beats[0]["shots"][0]["start"] = 0.0
    for current, following in zip(beats, beats[1:]):
        next_start = float(following["start"])
        if next_start > float(current["end"]) and current.get("shots"):
            current["end"] = round(next_start, 3)
            # Extend the last shot over the silence; preserve all spoken timing.
            current["shots"][-1]["end"] = round(
                current["end"] - float(current["start"]), 3
            )

    duration=max((b["end"] for b in beats),default=0)
    if duration<480: raise ValueError(f"Documentary is too short ({duration/60:.1f} min).")
    if duration>1800: raise ValueError(f"Documentary is too long ({duration/60:.1f} min).")
    m={"version":2,"title":plan.get("title",plan["topic"]),"topic":plan["topic"],"duration":round(duration,3),"fps":profile["fps"],"width":profile["width"],"height":profile["height"],"audioSrc":audio_src,"beats":beats,"captions":words,"showCaptions":True,"showProgressBar":False,"sources":plan.get("sources",[])}
    Path(out).write_text(json.dumps(m,indent=2),encoding="utf-8");return out