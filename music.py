from __future__ import annotations
import os,requests
from pathlib import Path

def get_music(query:str,out:Path)->Path|None:
    # Optional provider hook. No copyrighted music is bundled with the repository.
    return None
