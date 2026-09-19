import {useEffect,useRef,useState} from 'react';
import {Application,Assets,Container,Graphics,Sprite,Text,Texture,Rectangle} from 'pixi.js';
import {Maximize,Minimize,Minus,Plus,LocateFixed,Eye,EyeOff,Pause,Play,Mountain} from 'lucide-react';
import {Agent,World,stages} from './types';
import {minerTexture} from './sprites';
const W=1264,H=700;
const nodes=[[215,523],[343,323],[595,246],[790,385],[1048,492],[616,587]];
const deepNodes=[[215,523],[927,317],[1056,271],[890,383],[1048,492],[616,587]];
const carefulNodes=[[215,523],[331,350],[383,292],[657,374],[1048,492],[616,587]];
export const MineScene=({world,onSelect}:{world:World|null;onSelect:(a:Agent)=>void})=>{
 const host=useRef<HTMLDivElement>(null),frame=useRef<HTMLDivElement>(null),latest=useRef(world),select=useRef(onSelect);
 const settings=useRef({zoom:1,labels:true,motion:true});
 const clockOffset=useRef(0);
 useEffect(()=>{if(world)clockOffset.current=world.server_time-Date.now()/1000;},[world]);
 const [zoom,setZoom]=useState(1),[labels,setLabels]=useState(true),[motion,setMotion]=useState(()=>!window.matchMedia('(prefers-reduced-motion: reduce)').matches),[full,setFull]=useState(false),[ready,setReady]=useState(false),[failed,setFailed]=useState(false);
 latest.current=world;select.current=onSelect;settings.current={zoom,labels,motion};
 useEffect(()=>{const listener=()=>setFull(Boolean(document.fullscreenElement));document.addEventListener('fullscreenchange',listener);return()=>document.removeEventListener('fullscreenchange',listener);},[]);
 useEffect(()=>{
  let cancelled=false,initialized=false;const app=new Application();
  const sprites=new Map<string,{root:Container;body:Sprite;tool:Graphics;cart:Graphics;spark:Graphics;label:Text;ring:Graphics;textures:Texture[];lastX:number}>();
  const textures:Texture[]=[];
  const run=async()=>{
   try{
    await app!.init({width:W,height:H,background:0x17191b,antialias:false,resolution:1,preference:'webgl',roundPixels:true});initialized=true;
    if(cancelled){app!.destroy(true);return;}
    host.current?.appendChild(app!.canvas);app!.canvas.setAttribute('data-testid','mine-canvas');app!.canvas.setAttribute('aria-label','Live underground mine with autonomous pixel miners');
    const terrain=await Assets.load('/assets/underground.jpg');if(cancelled)return;
    const scene=new Container();app!.stage.addChild(scene);
    const bg=new Sprite(terrain);bg.width=W;bg.height=H;scene.addChild(bg);
    const actors=new Container();scene.addChild(actors);actors.sortableChildren=true;
    const fire=new Graphics();scene.addChild(fire);
    let visualTime=0,previousZoom=1;
    app!.ticker.maxFPS=45;
    app!.ticker.add((ticker)=>{
     if(!app||cancelled)return;
     const cfg=settings.current;
     if(cfg.motion)visualTime+=ticker.deltaMS/1000;
     previousZoom+=(cfg.zoom-previousZoom)*0.12;
     scene.scale.set(previousZoom);scene.position.set(W/2*(1-previousZoom),H/2*(1-previousZoom));
     const data=latest.current;
     if(!data)return;
     const now=Date.now()/1000+clockOffset.current;
     const occupiedLabels:{x:number;y:number;w:number;h:number}[]=[];
     data.agents.forEach((agent,index)=>{
      let item=sprites.get(agent.id);
      if(!item){
       const root=new Container();root.eventMode='static';root.cursor='pointer';root.hitArea=new Rectangle(-26,-46,52,60);
       root.on('pointertap',()=>{const a=latest.current?.agents.find(a=>a.id===agent.id);if(a)select.current(a);});
       const tex=[0,1,2].map(p=>{const t=Texture.from(minerTexture(agent.avatar,p));t.source.scaleMode='nearest';textures.push(t);return t;});
       const ring=new Graphics().ellipse(0,6,22,7).fill({color:0x090c0b,alpha:.35});root.addChild(ring);
       const body=new Sprite(tex[0]);body.anchor.set(.5,.85);body.scale.set(1.18);root.addChild(body);
       const tool=new Graphics().rect(-2,-12,3,23).fill(0x9e7851).rect(-11,-15,19,4).fill(0xb8c2c3).rect(5,-11,4,4).fill(0x78888b);tool.position.set(19,-13);root.addChild(tool);
       const cart=new Graphics().rect(22,-7,28,13).fill(0x333d40).rect(21,-8,30,3).fill(0x89908a).rect(25,-15,7,7).fill(0xb3944f).rect(33,-18,6,10).fill(0xd6b45e).rect(40,-14,6,7).fill(0xc19b47).rect(25,5,6,6).fill(0x232b30).rect(41,5,6,6).fill(0x232b30).rect(24,-3,24,2).fill(0x5f6a69);root.addChild(cart);
       const spark=new Graphics();root.addChild(spark);
       const label=new Text({text:agent.name,style:{fontFamily:'JetBrains Mono, monospace',fontSize:12,fill:agent.is_bot?0xe0dfd3:0xf7cf7b,stroke:{color:0x151819,width:4},fontWeight:'500'}});label.anchor.set(.5,1);label.position.set(0,-37);root.addChild(label);
       actors.addChild(root);item={root,body,tool,cart,spark,label,ring,textures:tex,lastX:0};sprites.set(agent.id,item);
      }
      const stage=agent.status==='ready'?0:Math.max(0,stages.indexOf(agent.stage)),prev=agent.is_bot?(stage+5)%6:Math.max(0,stages.indexOf(agent.previous_stage));
      const progress=agent.status==='active'?Math.max(0,Math.min(1,(now-agent.stage_started_at)/18)):1;
      const walk=agent.status==='active'&&progress<.43;
      const offsetX=((index*37)%91)-45,offsetY=((index*17)%35)-17;
      const route=agent.preference==='deep'?deepNodes:agent.preference==='careful'?carefulNodes:nodes;
      const goal=route[stage],start=route[prev];const p=walk?progress/.43:1;const smooth=p*p*(3-2*p);
      const x=start[0]+(goal[0]-start[0])*smooth+offsetX;
      const y=start[1]+(goal[1]-start[1])*smooth+offsetY;
      if(cfg.motion||item.lastX===0){item.root.position.set(x,y+(walk?Math.sin(visualTime*12+index)*1.5:0));item.lastX=x;}
      item.root.zIndex=item.root.y;item.body.texture=item.textures[walk&&cfg.motion?1+Math.floor(visualTime*7)%2:0];
      const labelBox={x:item.root.x-item.label.width/2-4,y:item.root.y-54,w:item.label.width+8,h:20};
      item.label.visible=cfg.labels&&occupiedLabels.every(b=>labelBox.x+labelBox.w<b.x||labelBox.x>b.x+b.w||labelBox.y+labelBox.h<b.y||labelBox.y>b.y+b.h);
      if(item.label.visible)occupiedLabels.push(labelBox);
      item.tool.visible=!walk&&(stage===2||stage===5)&&agent.status==='active';
      item.cart.visible=(stage===3||(stage===4&&walk))&&agent.status==='active';
      item.tool.rotation=cfg.motion?Math.sin(visualTime*(stage===2?5:2.5)+index)*.9:.4;
      item.spark.clear();
      if(item.tool.visible&&cfg.motion&&Math.sin(visualTime*5+index)>.8){for(let j=0;j<3;j++)item.spark.rect(21+j*5,-6-j*3,2,2).fill({color:0xf8ca68,alpha:.8-j*.15});}
      item.body.tint=agent.status==='paused'?0x9b9b9b:0xffffff;
     });
     fire.clear();
     if(cfg.motion){for(let i=0;i<7;i++){const p=(visualTime*.26+i*.15)%1;fire.rect(1065+Math.sin(i*12.5)*14,433-p*65,3,3).fill({color:i%2?0xe3ac55:0xe8cd82,alpha:(1-p)*.8});}}
    });
    setReady(true);
   }catch(e){if(!cancelled){setFailed(true);console.error('Mine renderer:',e);}}
  };run();
  return()=>{cancelled=true;if(initialized){app.destroy(true,{children:true,texture:false,textureSource:false});textures.forEach(t=>t.destroy(true));}};
 },[]);
 const fullscreen=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await frame.current?.requestFullscreen();}catch{setFailed(true);}};
 return <section ref={frame} className={`mine-frame ${full?'is-fullscreen':''}`} data-testid="mine-world-panel">
  <div className="map-heading"><div className="section-title"><Mountain size={16}/><h2 data-testid="mine-map-title">The Underground</h2><span className="sector" data-testid="mine-sector">SECTOR 01</span></div><span className="live-tag" data-testid="map-live-status"><i/>{world?.worker_online?'LIVE WORLD':'CONNECTING'}</span></div>
  <div className="scene-wrap"><div ref={host} className="pixi-host" data-testid="mine-scene"/>
   {!ready&&<div className="scene-loading" data-testid="scene-loading"><Mountain size={28}/><span>{failed?'The mine view could not load. Please refresh.':'Opening the underground…'}</span></div>}
   <div className="map-coordinate" data-testid="map-coordinates"><span>THE BRASS HOLLOW</span><small>47° 12′ N · DEPTH 120 M</small></div>
   <div className="map-key" data-testid="map-legend"><i className="gold-dot"/>Gold seam<i className="teal-dot"/>Crystal vein</div>
   <div className="map-controls"><button data-testid="map-zoom-in" title="Zoom in" aria-label="Zoom in" disabled={zoom>=1.6} onClick={()=>setZoom(z=>Math.min(1.6,z+.2))}><Plus size={16}/></button><button data-testid="map-zoom-out" title="Zoom out" aria-label="Zoom out" disabled={zoom<=1} onClick={()=>setZoom(z=>Math.max(1,z-.2))}><Minus size={16}/></button><span/><button data-testid="map-reset-view" title="Reset view" aria-label="Reset view" onClick={()=>setZoom(1)}><LocateFixed size={16}/></button><button data-testid="map-fullscreen" title={full?'Exit full screen':'Full screen'} aria-label={full?'Exit full screen':'Full screen'} onClick={fullscreen}>{full?<Minimize size={16}/>:<Maximize size={16}/>}</button></div>
  </div>
  <div className="map-footer"><span data-testid="map-crew-count"><i className="status-dot"/>{world?.active_agents ?? '—'} agents on shift <span className="muted">· Shared world</span></span><div><button data-testid="map-toggle-labels" aria-label="Toggle miner names" aria-pressed={labels} title="Miner names" onClick={()=>setLabels(v=>!v)}>{labels?<Eye size={14}/>:<EyeOff size={14}/>}<span>Names</span></button><button data-testid="map-toggle-animation" title={motion?'Pause animation':'Resume animation'} aria-label={motion?'Pause animation':'Resume animation'} onClick={()=>setMotion(v=>!v)}>{motion?<Pause size={14}/>:<Play size={14}/>}<span>{motion?'Pause view':'Resume view'}</span></button></div></div>
 </section>;
};