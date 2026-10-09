from __future__ import annotations
import random,re
from typing import Any

def plan_edits(beats:list[dict],seed:int=42)->list[dict]:
    random.seed(seed); out=[]
    for i,b in enumerate(beats):
        intensity=float(b.get("intensity",.6)); n=max(2,min(8,int(2+intensity*5)))
        actions=[]
        for j in range(n):
            actions.append({"type":random.choice(["cut","zoom","pan","flash","shake","paper","freeze","mask"]),
              "at":round(j/max(1,n-1),3),"duration":round(random.uniform(.08,.42),2),
              "intensity":round(min(1,intensity*random.uniform(.7,1.15)),2)})
        b["actions"]=actions
        b["sfx"]=[]
        out.append(b)
    return out
