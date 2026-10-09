import React from "react";
import {AbsoluteFill,Audio,Img,OffthreadVideo,interpolate,useCurrentFrame,useVideoConfig,staticFile} from "remotion";
import type {VideoManifest,Beat,Shot,Layer} from "./types";

const src=(s:string)=>s.startsWith("http")?s:staticFile(s);
const shadow="0 8px 36px rgba(0,0,0,.9)";
const textShadow="0 3px 18px rgba(0,0,0,.95)";
const clamp=(x:number,a=0,b=1)=>Math.max(a,Math.min(b,x));
const ease=(x:number)=>x*x*(3-2*x);

const LayerView:React.FC<{layer:Layer;beat:Beat;shot:Shot;frame:number;fps:number}>=({layer,beat,shot,frame,fps})=>{
 const local=Math.max(0,frame/fps-(beat.start+shot.start)),d=Math.max(.01,shot.end-shot.start);
 const reveal=ease(clamp(local/.28));
 const sc=layer.animation==="push"?interpolate(local,[0,d],[1.12,1.01],{extrapolateRight:"clamp"}):
          layer.animation==="pull"?interpolate(local,[0,d],[1.01,1.10],{extrapolateRight:"clamp"}):1;
 const panX=layer.animation==="pan"?interpolate(local,[0,d],[-3,3],{extrapolateRight:"clamp"}):0;
 const panY=layer.animation==="parallax"?interpolate(local,[0,d],[2,-2],{extrapolateRight:"clamp"}):0;
 const base:React.CSSProperties={position:"absolute",left:`${layer.x}%`,top:`${layer.y}%`,width:`${layer.width}%`,height:`${layer.height}%`,opacity:(layer.opacity??1)*reveal,zIndex:layer.z,transform:`translate(${panX}%,${panY}%) rotate(${layer.rotation}deg) scale(${sc})`,transformOrigin:"center center"};
 if(layer.kind==="image"&&layer.assetId){
  const a=beat.assets.find(x=>x.id===layer.assetId);
  if(!a)return null;
  const media=a.kind==="video"
   ? <OffthreadVideo src={src(a.src)} muted startFrom={0} style={{width:"100%",height:"100%",objectFit:"cover",display:"block"}}/>
   : <Img src={src(a.src)} style={{width:"100%",height:"100%",objectFit:"cover",display:"block"}}/>;
  return <div style={{...base,overflow:"hidden",borderRadius:layer.width<70?18:0,boxShadow:layer.width<70?shadow:"0 0 0 transparent",background:"#111"}}>
   {media}
   <div style={{position:"absolute",inset:0,background:"linear-gradient(180deg,rgba(0,0,0,.04),transparent 55%,rgba(0,0,0,.5))"}}/>
  </div>;
 }
 if(layer.kind==="highlight")return <div style={{...base,background:"linear-gradient(90deg,rgba(245,205,40,.55),rgba(245,205,40,.08))",mixBlendMode:"screen",filter:"blur(.3px)"}}/>;
 if(layer.kind==="arrow")return <div style={{...base,color:"#fff",fontSize:"4vw",fontWeight:900,textShadow}}>{layer.text||"→"}</div>;
 if(layer.kind==="label")return <div style={{...base,boxSizing:"border-box",background:"rgba(8,8,8,.72)",border:"1px solid rgba(255,255,255,.28)",borderRadius:7,padding:"7px 11px",fontFamily:"monospace",fontWeight:800,fontSize:"1.05vw",letterSpacing:2,color:"#fff",backdropFilter:"blur(12px)"}}>{layer.text}</div>;
 if(layer.kind==="text")return <div style={{...base,fontFamily:"Arial Black,Arial",fontWeight:900,fontSize:"clamp(34px,5vw,96px)",lineHeight:.9,letterSpacing:-3,color:"#f5f2ea",textTransform:"uppercase",textShadow,display:"flex",alignItems:"flex-end"}}>{layer.text}</div>;
 return null;
};

const ShotView:React.FC<{beat:Beat;shot:Shot;frame:number;fps:number}>=({beat,shot,frame,fps})=>{
 const local=frame/fps-(beat.start+shot.start),d=shot.end-shot.start;
 const flash=shot.actions.find(a=>a.type==="flash"),shake=shot.actions.find(a=>a.type==="shake");
 const zoom=shot.actions.find(a=>a.type==="zoom"),blur=shot.actions.find(a=>a.type==="blur"),glitch=shot.actions.find(a=>a.type==="glitch"),whip=shot.actions.find(a=>a.type==="whip");
 const zoomScale=zoom?1+zoom.intensity*.12*clamp(local/Math.max(.01,zoom.duration)):1;
 const blurPx=blur?blur.intensity*5:0;
 const glitchX=glitch?Math.sin(local*170)*glitch.intensity*7:0;
 const whipX=whip?interpolate(local,[Math.max(0,whip.at*d-.10),Math.max(.01,whip.at*d)],[0,whip.intensity*90],{extrapolateLeft:"clamp",extrapolateRight:"clamp"}):0;
 const fp=flash?interpolate(local,[flash.at*d,flash.at*d+flash.duration],[.42,0],{extrapolateLeft:"clamp",extrapolateRight:"clamp"}):0;
 const dx=shake?Math.sin(local*80)*shake.intensity*10:0;
 return <AbsoluteFill style={{overflow:"hidden",background:"#080808",transform:`translate(${dx+glitchX+whipX}px,0) scale(${zoomScale})`,filter:`blur(${blurPx}px)`}}>
  <AbsoluteFill style={{background:"radial-gradient(circle at 50% 45%,rgba(255,255,255,.035),transparent 55%)"}}/>
  {shot.layers.map(l=><LayerView key={l.id} layer={l} beat={beat} shot={shot} frame={frame} fps={fps}/>)}
  {fp>0&&<AbsoluteFill style={{background:"#fff",opacity:fp,zIndex:30}}/>}
  {glitch&&<AbsoluteFill style={{opacity:.12,mixBlendMode:"screen",transform:`translateX(${-glitchX}px)`,background:"linear-gradient(transparent 46%,rgba(255,255,255,.8) 47%,transparent 49%,transparent 52%,rgba(255,255,255,.35) 53%,transparent 55%)",zIndex:31}}/>}
  {shot.actions.some(a=>a.type==="freeze")&&<AbsoluteFill style={{background:"#fff",opacity:interpolate(local,[0,.06,.14],[0,.08,0],{extrapolateLeft:"clamp",extrapolateRight:"clamp"}),zIndex:29}}/>}
  {shot.actions.some(a=>a.type==="paper")&&<AbsoluteFill style={{background:"linear-gradient(135deg,rgba(245,240,225,.12),transparent 35%,rgba(255,255,255,.04))",mixBlendMode:"screen",zIndex:28}}/>}
  {shot.actions.some(a=>a.type==="mask")&&<AbsoluteFill style={{background:"radial-gradient(circle at 50% 50%,transparent 0 42%,rgba(0,0,0,.88) 72%)",zIndex:27}}/>}
  <AbsoluteFill style={{pointerEvents:"none",boxShadow:"inset 0 0 220px rgba(0,0,0,.78)",zIndex:32}}/>
  <AbsoluteFill style={{pointerEvents:"none",background:"linear-gradient(180deg,rgba(0,0,0,.28),transparent 24%,transparent 76%,rgba(0,0,0,.42))",zIndex:33}}/>
 </AbsoluteFill>;
};

const cap=(w:any[],t:number)=>w.find((x:any)=>t>=x.start&&t<x.end)?.word||"";

export const JackPocketsVideo:React.FC<{manifest:VideoManifest}>=({manifest})=>{
 const frame=useCurrentFrame(),{fps}=useVideoConfig(),time=frame/fps;
 const activeBeat=manifest.beats.find(b=>time>=b.start&&time<b.end);
 const activeShot=activeBeat?.shots.find(s=>time>=activeBeat.start+s.start&&time<activeBeat.start+s.end);
 const activeShotFrame=activeBeat&&activeShot ? frame-Math.round((activeBeat.start+activeShot.start)*fps) : 0;
 const caption=cap(manifest.captions,time);
 return <AbsoluteFill style={{background:"#101010",overflow:"hidden"}}>
  {activeBeat&&activeShot&&<ShotView beat={activeBeat} shot={activeShot} frame={frame} fps={fps}/>}
  {activeBeat&&activeShot&&activeShot.layers.length===0&&<AbsoluteFill style={{background:"linear-gradient(135deg,#171717,#050505)",zIndex:40}}/>}
  {!activeBeat&&<AbsoluteFill style={{background:"#101010",zIndex:40}}/>}
  <AbsoluteFill style={{pointerEvents:"none",zIndex:80}}>
   {activeBeat&&<div style={{position:"absolute",left:"6%",top:"5%",fontFamily:"Arial Black,Arial",fontSize:"18px",fontWeight:900,letterSpacing:3,color:"rgba(255,255,255,.65)",textTransform:"uppercase"}}>{activeBeat.kind}</div>}
   {activeBeat&&<div style={{position:"absolute",left:"6%",right:"12%",bottom:"13%",fontFamily:"Arial Black,Arial",fontSize:"clamp(28px,3.2vw,64px)",fontWeight:900,lineHeight:.98,color:"#fff",textShadow}}>{activeBeat.narration.slice(0,110)}</div>}
   {caption&&<div style={{position:"absolute",left:"9%",right:"9%",bottom:"5.5%",height:64,display:"flex",alignItems:"center",justifyContent:"center",fontFamily:"Arial Black,Arial",fontSize:"clamp(22px,2.25vw,42px)",fontWeight:900,color:"#fff",textShadow:"0 3px 14px #000",textAlign:"center"}}>{caption}</div>}
   <div style={{position:"absolute",left:0,right:0,bottom:0,height:4,background:"rgba(255,255,255,.18)"}}><div style={{height:"100%",width:`${Math.min(100,time/manifest.duration*100)}%`,background:"#f5d76e"}}/></div>
  </AbsoluteFill>
  {manifest.audioSrc&&<Audio src={staticFile(manifest.audioSrc)}/>}
  {manifest.musicSrc&&<Audio src={staticFile(manifest.musicSrc)} volume={()=>.045+(1-(activeBeat?.intensity??.5))*.07}/>} 
  {activeBeat&&activeShot&&activeShot.sfx?.map((fx,i)=>fx.src?<Audio key={`sfx-${activeShot.id}-${i}`} src={staticFile(fx.src)} startFrom={0} volume={fx.gain}/>:null)}
 </AbsoluteFill>;
};
