from __future__ import annotations
import json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

def fallback(topic:str)->dict:
 return {"title":topic,"beats":[
 {"kind":"cold-open","narration":f"What if the most ordinary part of {topic} hides the strangest story?","intensity":1,"keywords":[topic],"overlays":[{"type":"headline","text":"THE STRANGE PART"}]},
 {"kind":"context","narration":"Before the story gets weird, there is context we need.","intensity":.55,"keywords":["context"],"overlays":[{"type":"label","text":"CONTEXT"}]},
 {"kind":"escalation","narration":"Then the details start stacking up.","intensity":.75,"keywords":["timeline"],"overlays":[{"type":"stat","text":"THE TIMELINE"}]},
 {"kind":"reveal","narration":"And that is where the story changes.","intensity":1,"keywords":["reveal"],"overlays":[{"type":"stamp","text":"REVEAL"}]},
 {"kind":"fallout","narration":"The consequences did not stop there.","intensity":.8,"keywords":["impact"],"overlays":[{"type":"label","text":"AFTERMATH"}]},
 {"kind":"ending","narration":"Sometimes the strangest stories are hiding in plain sight.","intensity":.5,"keywords":["ending"],"overlays":[{"type":"headline","text":"THAT'S THE STORY"}]}
 ]}

# Backwards-compatible name for older callers.
fallback_plan=fallback

def generate(topic:str,out:Path)->Path:
 out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(fallback(topic),indent=2),encoding="utf-8"); return out

if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser(); p.add_argument("--topic",required=True); p.add_argument("--out",default="data/runs/script.json"); a=p.parse_args(); print(generate(a.topic,Path(a.out)))
