import {useEffect,useRef} from 'react';
import {drawMiner} from './sprites';
export const Avatar=({avatar='brass',size=48,className=''}:{avatar?:string;size?:number;className?:string})=>{
 const ref=useRef<HTMLCanvasElement>(null);
 useEffect(()=>{const c=ref.current?.getContext('2d');if(c){c.clearRect(0,0,36,34);drawMiner(c,avatar);}},[avatar]);
 return <canvas ref={ref} width={36} height={34} style={{width:size,height:size*34/36}} className={`pixel-avatar ${className}`} aria-hidden="true"/>;
};