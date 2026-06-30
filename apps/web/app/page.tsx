'use client'
import { useState } from 'react'
export default function Page(){
  const [input,setInput] = useState('Investigate checkout latency spike in us-east')
  const [output,setOutput] = useState('')
  const [loading,setLoading] = useState(false)
  const api = process.env.NEXT_PUBLIC_API_URL || 'https://aegis-api-two.vercel.app'
  const run = async ()=>{
    setLoading(true); setOutput('')
    const res = await fetch(api+'/stream', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({input, thread_id:'web-'+Date.now()})})
    if(!res.body){ setOutput('No stream'); setLoading(false); return}
    const reader = res.body.getReader(); const decoder = new TextDecoder()
    while(true){ const {done,value} = await reader.read(); if(done) break; const chunk = decoder.decode(value); chunk.split('\n\n').forEach(line=>{ if(line.startsWith('data: ')){ try{ const j=JSON.parse(line.slice(6)); if(j.token) setOutput(o=>o+j.token)}catch{}}})}
    setLoading(false)
  }
  return (
    <main style={{fontFamily:'system-ui', maxWidth:780, margin:'40px auto', padding:20}}>
      <h1>AEGIS — Autonomous Enterprise Graph Intelligence</h1>
      <p>Multi-agent operations cortex — LangGraph Supervisor + 6 specialists</p>
      <textarea value={input} onChange={e=>setInput(e.target.value)} style={{width:'100%', height:80}}/>
      <button onClick={run} disabled={loading} style={{padding:'10px 18px', marginTop:8}}>{loading?'Running…':'Run AEGIS'}</button>
      <pre style={{whiteSpace:'pre-wrap', background:'#f6f6f6', padding:16, marginTop:16, minHeight:120}}>{output || 'Output will stream here…'}</pre>
      <p style={{fontSize:13, color:'#666'}}>API: <a href={api+'/docs'}>{api}/docs</a> — HITL: POST /threads/{'{id}'}/resume</p>
    </main>
  )
}
