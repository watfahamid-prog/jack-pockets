from __future__ import annotations
import os,requests

def search_web(query:str,limit:int=6)->list[dict]:
    key=os.getenv("TAVILY_API_KEY")
    if not key:return []
    r=requests.post("https://api.tavily.com/search",json={"api_key":key,"query":query,"max_results":limit,"search_depth":"advanced"},timeout=45)
    r.raise_for_status()
    return [{"title":x.get("title"),"url":x.get("url"),"content":x.get("content","")} for x in r.json().get("results",[])]
