from __future__ import annotations
import html, os, re, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

def _pexels_key()->str:
    key=os.getenv("PEXELS_API_KEY","").strip()
    print(f"[pexels] key configured={'yes' if key else 'no'}")
    return key

def _get(url:str,key:str,params:dict)->dict:
    r=requests.get(url,headers={"Authorization":key},params=params,timeout=45)
    if not r.ok:
        raise RuntimeError(f"Pexels HTTP {r.status_code}: {r.text[:240].replace(chr(10),' ')}")
    return r.json()

def _download(url,path):
    with requests.get(url,timeout=90,stream=True) as r:
        r.raise_for_status()
        with path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                if chunk:f.write(chunk)

def search_pexels_videos(query:str,out:Path,limit:int=2)->list[dict]:
    key=_pexels_key()
    if not key:
        print("[pexels] no API key; skipping video search")
        return []
    out.mkdir(parents=True,exist_ok=True)
    print(f"[pexels] video search: {query[:120]!r}")
    data=_get("https://api.pexels.com/v1/videos/search",key,{"query":query[:180],"per_page":max(3,limit*3),"orientation":"landscape","size":"medium","locale":"en-US"})
    videos=data.get("videos",[])
    print(f"[pexels] video results={len(videos)} total={data.get('total_results',0)}")
    result=[]
    for video in videos:
        files=[f for f in video.get("video_files",[]) if f.get("file_type")=="video/mp4" and f.get("link")]
        files.sort(key=lambda f:(f.get("width",0)>=1280,f.get("width",0)*f.get("height",0),f.get("fps",0)),reverse=True)
        chosen=files[0] if files else None
        if not chosen: continue
        vid=str(video.get("id"))
        path=out/f"video-{vid}.mp4"
        try:
            if not path.exists(): _download(chosen["link"],path)
            print(f"[pexels] selected video={vid} {chosen.get('width')}x{chosen.get('height')} duration={video.get('duration')}s bytes={path.stat().st_size}")
            result.append({"id":f"pexels-video-{vid}","kind":"video","src":str(path),"credit":(video.get("user") or {}).get("name"),"license":"Pexels","score":1.0,"role":"b-roll","duration":float(video.get("duration") or 0),"width":chosen.get("width"),"height":chosen.get("height"),"fps":chosen.get("fps")})
            if len(result)>=limit: break
        except Exception as e:
            print(f"[pexels] download failed video={vid}: {e}")
    return result

def search_pexels(query:str,out:Path,limit:int=3)->list[dict]:
    key=_pexels_key()
    if not key:
        print("[pexels] no API key; skipping photo search")
        return []
    out.mkdir(parents=True,exist_ok=True)
    print(f"[pexels] photo search: {query[:120]!r}")
    data=_get("https://api.pexels.com/v1/search",key,{"query":query[:180],"per_page":max(1,limit),"orientation":"landscape","locale":"en-US"})
    result=[]
    for p in data.get("photos",[]):
        src=p.get("src",{}).get("large2x") or p.get("src",{}).get("large")
        if not src: continue
        path=out/f"photo-{p['id']}.jpg"
        try:
            _download(src,path)
            result.append({"id":str(p["id"]),"kind":"photo","src":str(path),"credit":p.get("photographer"),"license":"Pexels","score":1.0,"role":"b-roll"})
        except Exception as e:
            print(f"[pexels] photo download failed id={p.get('id')}: {e}")
    return result

def make_asset_plan(sentence:str,editorial:dict|None=None)->list[dict]:
    low=sentence.lower();roles=[]
    if editorial:
        roles.extend(str(x).lower() for x in (editorial.get("visual_roles") or editorial.get("visuals") or []) if x)
    if any(x in low for x in ["map","country","city","where","location","border","north","south","east","west"]): roles.append("map")
    if any(x in low for x in ["according","report","document","letter","record","court","file","study","paper"]): roles.append("document")
    if any(x in low for x in ["percent","million","billion","number","statistic","rate","times","increase","decrease"]): roles.append("chart")
    if any(x in low for x in ["tweet","post","website","message","app","screenshot","online"]): roles.append("screenshot")
    roles=[r for r in dict.fromkeys(roles) if r in {"map","document","chart","screenshot","quote card","headline","texture","b-roll","photo","archival photo"}]
    if not roles:roles=["b-roll","photo"]
    return [{"role":x,"query":sentence[:180]} for x in roles[:3]]

def _safe(s:str)->str:
    return html.escape(re.sub(r"\s+"," ",str(s)).strip())

def _svg(kind:str,title:str,body:str,accent:str="#f5d76e")->str:
    title=_safe(title)[:70];body=_safe(body)[:210]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#161616"/><stop offset="1" stop-color="#050505"/></linearGradient><filter id="s"><feDropShadow dx="0" dy="16" stdDeviation="20" flood-opacity=".55"/></filter></defs>
<rect width="1920" height="1080" fill="url(#g)"/><rect x="70" y="70" width="1780" height="940" rx="28" fill="#111" stroke="#444" stroke-width="2" filter="url(#s)"/>
<rect x="70" y="70" width="12" height="940" fill="{accent}"/><text x="130" y="170" fill="#fff" font-family="Arial,sans-serif" font-size="34" font-weight="800" letter-spacing="5">{kind.upper()}</text>
<text x="130" y="270" fill="#fff" font-family="Arial,sans-serif" font-size="72" font-weight="900">{title}</text>
<foreignObject x="130" y="330" width="1500" height="520"><div xmlns="http://www.w3.org/1999/xhtml" style="font:32px Arial;color:#bbb;line-height:1.45">{body}</div></foreignObject>
<circle cx="1710" cy="190" r="44" fill="{accent}" opacity=".9"/><circle cx="1710" cy="190" r="18" fill="#111"/>
</svg>'''

def generate_role_asset(role:str,narration:str,out:Path,research:list[dict]|None=None,index:int=0)->dict|None:
    role=role.lower();out.mkdir(parents=True,exist_ok=True)
    key=re.sub(r"[^a-z0-9]+","-",narration.lower()).strip("-")[:42] or "scene"
    path=out/f"{index}-{role.replace(' ','-')}-{key}.svg"
    snippet=(research or [{}])[0].get("content","") if research else ""
    if role in {"document","quote card","headline"}:
        source=(research or [{}])[0]
        source_title=source.get("title","Research source") if source else "Research source"
        source_url=source.get("url","") if source else ""
        body=(snippet[:420] or "Evidence treatment generated from the research context.")
        body += f"\n\nSOURCE: {source_title}"
        if source_url: body += f"\n{source_url}"
        svg=_svg("SOURCE / DOCUMENT",narration[:72],body)
    elif role=="screenshot":
        svg=_svg("SCREEN / ONLINE",narration[:72],"A stylized source surface used to visualize an online claim or interface without fabricating a real screenshot.")
    elif role=="chart":
        nums=re.findall(r"\d+(?:\.\d+)?%?|\$?\d+(?:\.\d+)?\s*(?:million|billion|thousand)",narration,re.I)
        bar_parts=[]
        for i,n in enumerate(nums[:6]):
            raw=re.sub(r"[^0-9.]","",n)
            value=float(raw or 10)
            height=min(500,int(value*3))
            y=780-height
            bar_parts.append(f'<rect x="{260+i*250}" y="{y}" width="110" height="{height}" rx="12" fill="#f5d76e"/>')
        bars="".join(bar_parts)
        fallback='<rect x="300" y="500" width="900" height="180" rx="20" fill="#f5d76e" opacity=".8"/>'
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><rect width="1920" height="1080" fill="#090909"/><text x="150" y="150" fill="#fff" font-family="Arial" font-size="40" font-weight="800">DATA / SCALE</text><text x="150" y="235" fill="#fff" font-family="Arial" font-size="62" font-weight="900">{_safe(narration[:55])}</text><line x1="220" y1="820" x2="1700" y2="820" stroke="#555" stroke-width="3"/>{bars or fallback}</svg>'
    elif role=="map":
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><rect width="1920" height="1080" fill="#0a0a0a"/><path d="M220 700 L400 430 L690 300 L980 390 L1210 270 L1510 470 L1680 730 L1450 870 L1040 820 L710 900 L390 820 Z" fill="#171717" stroke="#777" stroke-width="5"/><circle cx="980" cy="520" r="24" fill="#f5d76e"/><circle cx="980" cy="520" r="55" fill="none" stroke="#f5d76e" stroke-opacity=".35" stroke-width="5"/><text x="150" y="160" fill="#fff" font-family="Arial" font-size="40" font-weight="800">LOCATION</text><text x="150" y="235" fill="#fff" font-family="Arial" font-size="62" font-weight="900">{_safe(narration[:65])}</text></svg>'
    else:
        # Always provide a real visual fallback when stock footage is unavailable.
        # This prevents a valid render from becoming a completely black video.
        label = role.upper().replace("-", " ")
        title = _safe(narration[:78])
        body = _safe("Editorial visual generated from the narration. Stock footage can replace this asset when Pexels is configured.")
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#151515"/><stop offset="1" stop-color="#050505"/></linearGradient><radialGradient id="glow"><stop stop-color="#f5d76e" stop-opacity=".22"/><stop offset="1" stop-color="#f5d76e" stop-opacity="0"/></radialGradient></defs>
<rect width="1920" height="1080" fill="url(#bg)"/><circle cx="1540" cy="280" r="560" fill="url(#glow)"/>
<rect x="92" y="92" width="1736" height="896" rx="34" fill="#0d0d0d" fill-opacity=".72" stroke="#555" stroke-width="2"/>
<rect x="92" y="92" width="14" height="896" fill="#f5d76e"/>
<text x="150" y="190" fill="#f5d76e" font-family="Arial,sans-serif" font-size="34" font-weight="800" letter-spacing="6">{label}</text>
<text x="150" y="330" fill="#fff" font-family="Arial,sans-serif" font-size="68" font-weight="900">{title}</text>
<text x="150" y="900" fill="#999" font-family="Arial,sans-serif" font-size="28">{body}</text>
<circle cx="1530" cy="600" r="150" fill="none" stroke="#f5d76e" stroke-opacity=".45" stroke-width="5"/><circle cx="1530" cy="600" r="70" fill="#f5d76e" fill-opacity=".15" stroke="#f5d76e" stroke-width="3"/>
</svg>'''
    path.write_text(svg,encoding="utf-8")
    return {"id":f"generated-{index}-{role.replace(' ','-')}","kind":"generated","src":str(path),"role":role,"score":1.0,"credit":"Generated editorial graphic"}
