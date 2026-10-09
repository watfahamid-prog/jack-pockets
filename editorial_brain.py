from __future__ import annotations
import re,random
STOP={"the","a","an","and","or","but","of","to","in","on","for","with","is","was","are","were","this","that","it","as","at","by","from","into","about","then","than"}

def sentences(text:str)->list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+",text.strip()) if x.strip()]

def classify(s:str):
    low=s.lower()
    if any(x in low for x in ["but","however","except","instead","yet"]): return "contrast","evidence",.86
    if any(x in low for x in ["because","means","caused","after","before","according"]): return "explain","evidence",.68
    if any(x in low for x in ["suddenly","revealed","secret","actually","truth","discovered"]): return "reveal","reveal",.95
    if any(x in low for x in ["died","collapsed","lost","failed","ended","disappeared"]): return "consequence","consequence",.90
    if "?" in s:return "punchline","punchline",.90
    return "setup","setup",.52

def keywords(s:str)->list[str]:
    words=re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]{2,}",s)
    return list(dict.fromkeys(w.lower() for w in words if w.lower() not in STOP))[:6]

def _span(sentence,words,pos):
    target=re.findall(r"[a-z0-9]+",sentence.lower())
    flat=[re.sub(r"[^a-z0-9]","",str(w.get("word","")).lower()) for w in words]
    for i in range(pos,len(flat)):
        if flat[i:i+len(target)]==target:return i,i+len(target)
    return pos,min(len(words),pos+max(1,len(target)))

def _editorial_dict(value):
    if isinstance(value, list):
        return {"sentences":[x for x in value if isinstance(x,dict)]}
    if isinstance(value, dict):
        return value
    return {}

def build_shots(beat,seed=42,aligned_words=None,sentences_override=None):
    random.seed(seed+sum(ord(c) for c in beat.get("id","")))
    ss=sentences_override or sentences(str(beat.get("narration",""))) or [str(beat.get("narration",""))]
    total=max(.2,float(beat["end"])-float(beat["start"]))
    assets=beat.get("assets",[]);shots=[];pos=0
    for i,s in enumerate(ss):
        intent,reason,intensity=classify(s)
        if aligned_words:
            a,z=_span(s,aligned_words,pos);pos=z
            start=max(0,float(aligned_words[a]["start"])-float(beat["start"])) if a<len(aligned_words) else 0
            end=min(total,float(aligned_words[z-1]["end"])-float(beat["start"])) if z>a else start+.5
        else:
            start=sum(x["end"]-x["start"] for x in shots);end=start+max(.45,total/max(1,len(ss)))
        end=max(start+.25,end)
        if i==len(ss)-1:end=total
        aids=[a.get("id") for a in assets if a.get("id")]
        kw=keywords(s);layers=[]
        editorial=_editorial_dict(beat.get("editorial"))
        decisions=editorial.get("sentences") or editorial.get("shots") or editorial.get("edits") or []
        roles=editorial.get("visual_roles",[]) or editorial.get("visuals",[]) or []
        decision=decisions[i] if i<len(decisions) and isinstance(decisions[i],dict) else {}
        role=str(decision.get("visual_role") or decision.get("role") or (roles[i%len(roles)] if roles else ("document" if reason=="evidence" else "photo"))).lower()
        motion=str(decision.get("camera_motion") or decision.get("motion") or "").lower()
        layer_motion=motion if motion in {"push","pull","pan","parallax","whip"} else ("push" if intensity>.6 else ("pan" if i%2 else "parallax"))
        if aids:
            aid=aids[i%len(aids)]
            if role in ("document","screenshot","chart","map"):
                x,y,w,h=5,8,58,78;rot=-1 if role=="document" else 0
            elif len(aids)>1 and i%3==0:
                x,y,w,h=3,5,58,86;rot=-1
            else:
                x,y,w,h=0,0,100,100;rot=0
            layers.append({"id":f"img-{i}","kind":"image","assetId":aid,"x":x,"y":y,"width":w,"height":h,"rotation":rot,"opacity":1,"z":0,"animation":layer_motion})
            if len(aids)>1 and role in ("document","screenshot","chart","map"):
                aid2=aids[(i+1)%len(aids)]
                layers.append({"id":f"img-secondary-{i}","kind":"image","assetId":aid2,"x":66,"y":18,"width":29,"height":48,"rotation":1,"opacity":.96,"z":3,"animation":"pull"})
        if kw and role not in ("document","screenshot","chart","map"):
            layers.append({"id":f"kw-{i}","kind":"text","text":kw[0].upper(),"x":7,"y":70,"width":65,"height":18,"rotation":0,"opacity":.98,"z":5,"animation":"static"})
        if reason in ("evidence","reveal"):
            layers.append({"id":f"label-{i}","kind":"label","text":(role.upper()+" • "+reason.upper()),"x":7,"y":4,"width":34,"height":5,"rotation":0,"opacity":.9,"z":6,"animation":"static"})
        overlay_text=str(decision.get("overlay") or decision.get("text_overlay") or "").strip()
        if overlay_text:
            layers.append({"id":f"editorial-overlay-{i}","kind":"label","text":overlay_text[:70],"x":7,"y":12,"width":48,"height":7,"rotation":0,"opacity":.96,"z":7,"animation":"static"})
        if decision.get("highlight") and kw:
            layers.append({"id":f"editorial-focus-{i}","kind":"highlight","text":kw[0].upper(),"x":7,"y":59,"width":42,"height":9,"rotation":-1,"opacity":.72,"z":4,"animation":"static"})
        if intensity>.82:
            layers.append({"id":f"hl-{i}","kind":"highlight","text":kw[0].upper() if kw else "KEY DETAIL","x":7,"y":61,"width":38,"height":8,"rotation":-2,"opacity":.75,"z":4,"animation":"freeze"})
        acts=[{"type":"cut","at":0,"duration":.05,"intensity":intensity,"reason":reason},{"type":"zoom" if intensity>.65 else "pan","at":.12,"duration":min(.8,max(.2,(end-start)*.5)),"intensity":min(1,intensity*.65),"reason":"pace"}]
        if reason=="reveal":
            acts += [{"type":"flash","at":.82,"duration":.09,"intensity":.45,"reason":"reveal"},{"type":"glitch","at":.84,"duration":.12,"intensity":.18,"reason":"reveal"}]
        if intensity>.88:
            acts.append({"type":"shake","at":.84,"duration":.16,"intensity":.25,"reason":"emphasis"})
        shots.append({"id":f"{beat['id']}-shot-{i}","start":round(start,3),"end":round(end,3),"reason":reason,"intent":intent,"assetIds":aids,"layers":layers,"actions":acts,"sfx":[],"intensity":round(intensity,2)})
    beat["shots"]=shots
    return beat
