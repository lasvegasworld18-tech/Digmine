import {useCallback,useEffect,useState} from 'react';
import {Agent,World,JournalEvent} from './types';
const API = process.env.REACT_APP_BACKEND_URL + '/api';
type MyAgentResponse = {agent:Agent|null};
let sessionPending:Promise<string>|null = null;
export async function request<T>(path:string, options:RequestInit={}):Promise<T> {
 const token=localStorage.getItem('minepx-access');
 const response=await fetch(API+path,{...options,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`} : {}),...options.headers}});
 const data=await response.json();
 if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:'Please check your details and try again.');
 return data;
}
export async function ensureSession() {
 if(localStorage.getItem('minepx-access')) return localStorage.getItem('minepx-access');
 if(!sessionPending) sessionPending=request<{token:string}>('/session',{method:'POST'}).then(d=>{localStorage.setItem('minepx-access',d.token);return d.token;}).finally(()=>{sessionPending=null;});
 return sessionPending;
}
export function useMine() {
 const [world,setWorld]=useState<World|null>(null),[agent,setAgent]=useState<Agent|null>(null),[events,setEvents]=useState<JournalEvent[]>([]),[error,setError]=useState('');
 const refresh=useCallback(async()=>{
  try {
   const [w,j]=await Promise.all([request<World>('/world'),request<JournalEvent[]>('/journal?limit=40')]);
   setWorld(w);setEvents(j);
   if(localStorage.getItem('minepx-access')) {const me=await request<MyAgentResponse>('/agent');setAgent(me.agent);}
   setError('');
  } catch(e) {setError((e as Error).message || 'The mine is reconnecting. Please try again.');}
 },[]);
 useEffect(()=>{refresh();const id=setInterval(refresh,4000);return()=>clearInterval(id);},[refresh]);
 return {world,agent,events,error,refresh,setAgent};
}