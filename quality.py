from __future__ import annotations
import json
from pathlib import Path

def validate(path:str)->list[str]:
    m=json.loads(Path(path).read_text());e=[]
    if m.get("version")!=2:e.append("unsupported manifest version")
    if not m.get("beats"):e.append("manifest has no beats")
    if m.get("fps")!=60:e.append("output must be 60fps")
    if (m.get("width"),m.get("height"))!=(1920,1080):e.append("output must be 1920x1080")
    duration=float(m.get("duration",0))
    if duration<480:e.append("documentary is under 8 minutes")
    if duration>1800:e.append("documentary exceeds 30 minutes")
    if duration<=0:e.append("duration must be positive")
    if len(m.get("beats",[]))<8:e.append("long-form documentary needs at least 8 beats")
    if not m.get("captions"):e.append("missing Whisper captions")
    last=0; last_asset_ids=set()
    for b in m.get("beats",[]):
        if b["start"]<last-.05:e.append(f"overlapping beat: {b['id']}")
        if b["end"]<=b["start"]:e.append(f"invalid beat timing: {b['id']}")
        if not b.get("shots"):e.append(f"beat has no shots: {b['id']}")
        seen_roles=set()
        for s in b.get("shots",[]):
            if s["end"]<=s["start"]:e.append(f"invalid shot timing: {s['id']}")
            if s["start"]<-.05 or s["end"]>b["end"]-b["start"]+.1:e.append(f"shot outside beat: {s['id']}")
            if not s.get("layers"):e.append(f"shot has no visual layers: {s['id']}")
            if not s.get("assetIds"):e.append(f"shot has no asset: {s['id']}")
            if len(s.get("layers",[]))>1 and len(set(x.get("z") for x in s["layers"]))<len(s["layers"]):e.append(f"layer z-order collision: {s['id']}")
            for layer in s.get("layers",[]):
                if layer.get("assetId") and layer["assetId"] not in {x.get("id") for x in b.get("assets",[])}:e.append(f"missing asset reference: {s['id']} -> {layer['assetId']}")
            seen_roles.add(s.get("intent"))
        last=b["end"]
    if duration>0 and m.get("beats") and abs(float(m["beats"][-1]["end"])-duration)>.5:e.append("manifest duration does not match final beat")
    return sorted(set(e))
