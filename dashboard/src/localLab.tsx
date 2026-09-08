import React, { useMemo, useRef, useState } from 'react'
import { Download, FileUp, Play, SlidersHorizontal, X } from 'lucide-react'

type MarketRow = { date: string; open: number; high: number; low: number; close: number; volume: number }
type LabPoint = { date: string; value: number }
type LabTrade = { date: string; return: number; direction: number }

type LabResult = {
  source: string
  rows: number
  signal: string
  lookback: number
  feeBps: number
  delay: number
  totalReturn: number
  sharpe: number
  maxDrawdown: number
  winRate: number
  exposure: number
  turnover: number
  equity: LabPoint[]
  trades: LabTrade[]
}

const labels: Record<string,string> = {
  momentum: 'Momentum',
  mean_reversion: 'Mean reversion',
  abnormal_volume: 'Abnormal volume',
  volatility_breakout: 'Volatility breakout',
}

const sign = (x: number) => x > 0 ? 1 : x < 0 ? -1 : 0
const mean = (xs: number[]) => xs.length ? xs.reduce((a,b)=>a+b,0) / xs.length : 0
const std = (xs: number[]) => {
  if (xs.length < 2) return 0
  const m = mean(xs)
  return Math.sqrt(xs.reduce((a,b)=>a+(b-m)*(b-m),0) / xs.length)
}
const pct = (x:number, digits=1) => `${x >= 0 ? '+' : ''}${(x*100).toFixed(digits)}%`

function parseDate(raw: string): string | null {
  const v = raw.trim().replace(/^"|"$/g,'')
  if (!v) return null
  if (/^\d+(\.0+)?$/.test(v)) {
    let n = Number(v)
    if (!Number.isFinite(n)) return null
    if (n > 1e17) n /= 1_000_000 // nanoseconds -> milliseconds
    else if (n > 1e14) n /= 1000 // microseconds -> milliseconds
    else if (n < 1e11) n *= 1000 // seconds -> milliseconds
    const d = new Date(n)
    return Number.isFinite(d.getTime()) ? d.toISOString().slice(0,10) : null
  }
  const t = Date.parse(v)
  return Number.isFinite(t) ? new Date(t).toISOString().slice(0,10) : null
}

function detectDelimiter(line: string) {
  const counts = [[',',(line.match(/,/g)||[]).length], ['\t',(line.match(/\t/g)||[]).length], [';',(line.match(/;/g)||[]).length]] as const
  return [...counts].sort((a,b)=>b[1]-a[1])[0][0]
}

function splitCsvLine(line: string, delim: string): string[] {
  const out:string[] = []; let cur=''; let quote=false
  for (let i=0;i<line.length;i++) {
    const ch=line[i]
    if (ch==='"') {
      if (quote && line[i+1]==='"') { cur+='"'; i++ } else quote=!quote
    } else if (ch===delim && !quote) { out.push(cur); cur='' }
    else cur+=ch
  }
  out.push(cur)
  return out
}

function parseMarketCsv(text: string): MarketRow[] {
  const lines = text.split(/\r?\n/).filter(x=>x.trim())
  if (lines.length < 3) throw new Error('CSV is empty or too short.')
  const delim = detectDelimiter(lines[0])
  const first = splitCsvLine(lines[0], delim)
  const normalized = first.map(x=>x.trim().toLowerCase().replace(/[\s_-]+/g,''))
  const hasHeader = normalized.some(x=>['date','datetime','timestamp','opentime','close','volume'].includes(x))
  const aliases = (names:string[]) => normalized.findIndex(x=>names.includes(x))
  let idx = {date:-1,open:-1,high:-1,low:-1,close:-1,volume:-1}
  let start=0
  if (hasHeader) {
    idx = {
      date: aliases(['date','datetime','timestamp','time','opentime','unixtimestamp']),
      open: aliases(['open']), high: aliases(['high']), low: aliases(['low']),
      close: aliases(['close','adjclose','adjustedclose']),
      volume: aliases(['volume','volumefrom','basevolume','volumecrypto']),
    }
    start=1
  } else if (first.length >= 6) {
    // Native Binance kline layout: open_time, open, high, low, close, volume, ...
    idx = {date:0,open:1,high:2,low:3,close:4,volume:5}
  }
  if (idx.date < 0 || idx.close < 0 || idx.volume < 0) throw new Error('Need date/timestamp, close and volume columns (or raw Binance kline format).')
  const rows: MarketRow[]=[]
  for (let i=start;i<lines.length;i++) {
    const c=splitCsvLine(lines[i],delim)
    const date=parseDate(c[idx.date] ?? '')
    const close=Number((c[idx.close] ?? '').replace(/,/g,''))
    const volume=Number((c[idx.volume] ?? '').replace(/,/g,''))
    const open=idx.open>=0 ? Number(c[idx.open]) : close
    const high=idx.high>=0 ? Number(c[idx.high]) : close
    const low=idx.low>=0 ? Number(c[idx.low]) : close
    if (!date || ![open,high,low,close,volume].every(Number.isFinite) || close<=0 || volume<0) continue
    rows.push({date,open,high,low,close,volume})
  }
  rows.sort((a,b)=>a.date.localeCompare(b.date))
  const unique = [...new Map(rows.map(r=>[r.date,r])).values()]
  if (unique.length < 100) throw new Error(`Only ${unique.length} valid rows found; use at least 100 daily observations.`)
  return unique
}

function rollingZ(values:number[], i:number, lookback:number) {
  if (i+1 < lookback) return 0
  const window=values.slice(i-lookback+1,i+1)
  const s=std(window)
  return s ? (values[i]-mean(window))/s : 0
}

function buildSignals(rows:MarketRow[], signalName:string, lookback:number) {
  const closes=rows.map(r=>r.close), logClose=closes.map(Math.log), logVol=rows.map(r=>Math.log1p(r.volume))
  const rets=closes.map((c,i)=>i?c/closes[i-1]-1:0)
  const sig = rows.map((_r,i)=>{
    if (signalName==='momentum') return i>=lookback ? sign(closes[i]/closes[i-lookback]-1) : 0
    if (signalName==='mean_reversion') return -sign(rollingZ(logClose,i,lookback))
    if (signalName==='abnormal_volume') return rollingZ(logVol,i,lookback) > 1 ? sign(rets[i]) : 0
    if (signalName==='volatility_breakout') {
      if (i+1<lookback) return 0
      const vol=std(rets.slice(i-lookback+1,i+1))
      return vol && Math.abs(rets[i])/vol > 1 ? sign(rets[i]) : 0
    }
    return 0
  })
  return {sig,rets}
}

function runLab(rows:MarketRow[], source:string, signalName:string, lookback:number, feeBps:number, delay:number):LabResult {
  const {sig,rets}=buildSignals(rows,signalName,lookback)
  const held = rows.map((_r,i)=>i>=delay ? sig[i-delay] : 0)
  const equity:LabPoint[]=[]; const strat:number[]=[]; const trades:LabTrade[]=[]
  let eq=1, peak=1, maxDd=0, turnover=0, active=0, wins=0, activeRetCount=0
  for (let i=0;i<rows.length;i++) {
    const prevHeld=i?held[i-1]:0
    const turn=Math.abs(held[i]-prevHeld)
    turnover+=turn
    const sr=held[i]*rets[i]-turn*(feeBps/10000)
    strat.push(sr); eq*=1+sr; peak=Math.max(peak,eq); maxDd=Math.min(maxDd,eq/peak-1)
    if (held[i]!==0) active++
    if (held[i]!==0 || turn>0) {
      activeRetCount++
      if (sr>0) wins++
      trades.push({date:rows[i].date,return:sr,direction:held[i]})
    }
    equity.push({date:rows[i].date,value:eq})
  }
  const valid=strat.slice(Math.max(lookback+delay,1))
  const s=std(valid)
  const sharpe=s ? mean(valid)/s*Math.sqrt(365) : 0
  return {
    source,rows:rows.length,signal:signalName,lookback,feeBps,delay,totalReturn:eq-1,sharpe,maxDrawdown:maxDd,
    winRate:activeRetCount?wins/activeRetCount:0,exposure:active/rows.length,turnover,equity,trades,
  }
}

function LabChart({points}:{points:LabPoint[]}) {
  const w=900,h=210
  if (!points.length) return <div className="lab-empty">Run an experiment to generate an equity curve.</div>
  const vals=points.map(x=>x.value); let min=Math.min(...vals),max=Math.max(...vals)
  if (min===max) {min-=.01;max+=.01}
  const pad=(max-min)*.08;min-=pad;max+=pad
  const d=points.map((p,i)=>`${i?'L':'M'} ${(i/Math.max(points.length-1,1)*w).toFixed(2)} ${(h-(p.value-min)/(max-min)*h).toFixed(2)}`).join(' ')
  return <div className="lab-chart"><svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Local experiment equity curve">{[.25,.5,.75].map(y=><line key={y} x1="0" x2={w} y1={h*y} y2={h*y}/>) }<path d={d}/></svg><div><span>{points[0].date}</span><strong>{points.at(-1)?.value.toFixed(2)}×</strong><span>{points.at(-1)?.date}</span></div></div>
}

export default function LocalLab() {
  const [open,setOpen]=useState(true)
  const [rows,setRows]=useState<MarketRow[]>([])
  const [source,setSource]=useState('')
  const [signalName,setSignalName]=useState('momentum')
  const [lookback,setLookback]=useState(20)
  const [fee,setFee]=useState(10)
  const [delay,setDelay]=useState(1)
  const [result,setResult]=useState<LabResult|null>(null)
  const [message,setMessage]=useState('Import an OHLCV CSV to run a fresh browser-side backtest. Nothing leaves your device.')
  const inputRef=useRef<HTMLInputElement|null>(null)
  const ready=rows.length>=100
  const recentTrades=useMemo(()=>result?.trades.slice(-120) ?? [],[result])

  const importFile=async (file:File) => {
    try {
      const parsed=parseMarketCsv(await file.text())
      setRows(parsed);setSource(file.name);setResult(null)
      setMessage(`${parsed.length.toLocaleString()} daily rows loaded: ${parsed[0].date} → ${parsed.at(-1)?.date}.`)
    } catch (e) { setRows([]);setResult(null);setMessage(e instanceof Error?e.message:'Could not parse that file.') }
  }
  const run=()=>{ if (ready) setResult(runLab(rows,source,signalName,lookback,fee,delay)) }
  const exportResult=()=>{
    if (!result) return
    const blob=new Blob([JSON.stringify({...result,equity:result.equity.filter((_x,i)=>i%5===0||i===result.equity.length-1)},null,2)],{type:'application/json'})
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`signallab-${signalName}-${Date.now()}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),500)
  }

  return <section className={`local-lab ${open?'open':''}`}>
    <div className="lab-intro">
      <div><span className="eyebrow">LIVE RESEARCH WORKBENCH</span><h2>Run a strategy on your own market data</h2><p>Import daily OHLCV or raw Binance klines and recompute the backtest locally in the browser.</p></div>
      <button type="button" className="lab-toggle" onClick={()=>setOpen(x=>!x)}>{open?<><X size={15}/>Close lab</>:<><SlidersHorizontal size={15}/>Open interactive lab</>}</button>
    </div>
    {open && <div className="lab-body">
      <div className="lab-controls">
        <div className="lab-upload">
          <input ref={inputRef} type="file" accept=".csv,.txt" onChange={e=>{const f=e.target.files?.[0];if(f) void importFile(f)}} />
          <button type="button" onClick={()=>inputRef.current?.click()}><FileUp size={15}/>{source?'Replace CSV':'Load OHLCV CSV'}</button>
          <span>{message}</span>
        </div>
        <label>Signal<select value={signalName} onChange={e=>setSignalName(e.target.value)}>{Object.entries(labels).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
        <label>Lookback<select value={lookback} onChange={e=>setLookback(Number(e.target.value))}>{[5,10,20,40,60].map(x=><option key={x} value={x}>{x} days</option>)}</select></label>
        <label>Costs<select value={fee} onChange={e=>setFee(Number(e.target.value))}>{[0,5,10,15,25,50].map(x=><option key={x} value={x}>{x} bps</option>)}</select></label>
        <label>Execution<select value={delay} onChange={e=>setDelay(Number(e.target.value))}>{[1,2,3,5].map(x=><option key={x} value={x}>t+{x}</option>)}</select></label>
        <button type="button" className="run-lab" disabled={!ready} onClick={run}><Play size={14}/>Run experiment</button>
      </div>
      {result && <div className="lab-result">
        <div className="lab-kpis">
          <div><span>TOTAL RETURN</span><strong className={result.totalReturn>=0?'green':'red'}>{pct(result.totalReturn)}</strong></div>
          <div><span>SHARPE</span><strong>{result.sharpe.toFixed(2)}</strong></div>
          <div><span>MAX DRAWDOWN</span><strong className="red">{pct(result.maxDrawdown)}</strong></div>
          <div><span>WIN RATE</span><strong>{pct(result.winRate,0)}</strong></div>
          <div><span>EXPOSURE</span><strong>{pct(result.exposure,0)}</strong></div>
          <div><span>TURNOVER</span><strong>{result.turnover.toFixed(0)}×</strong></div>
        </div>
        <LabChart points={result.equity}/>
        <div className="lab-trades">{recentTrades.map((t,i)=><i key={`${t.date}-${i}`} className={t.return>0?'win':t.return<0?'loss':'flat'} title={`${t.date} · ${t.direction>0?'long':t.direction<0?'short':'flat'} · ${pct(t.return,2)}`}/>)}</div>
        <div className="lab-result-foot"><span><b>{source}</b> · {labels[result.signal]} · {result.lookback}d · {result.feeBps} bps · t+{result.delay}</span><button type="button" onClick={exportResult}><Download size={14}/>Export result</button></div>
        <div className="lab-warning">Local Lab is an exploratory fixed-parameter backtest. The main SignalLab research view uses the stricter walk-forward / inference pipeline.</div>
      </div>}
    </div>}
  </section>
}
