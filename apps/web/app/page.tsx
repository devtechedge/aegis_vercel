'use client'
import { useState } from 'react'
import { ThemeToggle } from './theme-toggle'
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
    <main className="shell">
      <header className="page-header">
        <div>
          <h1>AEGIS — Autonomous Enterprise Graph Intelligence</h1>
          <p>Multi-agent operations cortex — LangGraph Supervisor + 6 specialists</p>
        </div>
        <ThemeToggle />
      </header>
      <textarea value={input} onChange={e=>setInput(e.target.value)} />
      <button className="run" onClick={run} disabled={loading}>{loading?'Running…':'Run AEGIS'}</button>
      <pre className="out">{output || 'Output will stream here…'}</pre>
      <p className="meta">API: <a href={api+'/docs'}>{api}/docs</a> — HITL: POST /threads/{'{id}'}/resume</p>
    </main>
  )
}
