import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Activity, ArrowDownRight, ArrowUpRight, BarChart3, BrainCircuit, ChevronRight,
  CalendarDays, FlaskConical, Gauge, Layers3, Microscope, MousePointer2, RotateCcw, ShieldCheck, Sparkles,
  LayoutDashboard, BadgeCheck, SlidersHorizontal, Globe2, Grid3X3, UploadCloud
} from 'lucide-react'
import type { Payload, Point, Run } from './types'
import LocalLab from './localLab'
import './styles.css'

const signalLabels: Record<string, string> = {
  momentum: 'Momentum',
  mean_reversion: 'Mean reversion',
  abnormal_volume: 'Abnormal volume',
  volatility_breakout: 'Volatility breakout',
}

function pct(x: number, digits = 1) { return `${x >= 0 ? '+' : ''}${(x * 100).toFixed(digits)}%` }
function num(x: number | null | undefined, digits = 2) { return x == null ? '—' : x.toFixed(digits) }
function signed(x: number | null | undefined, digits = 2) { return x == null ? '—' : `${x >= 0 ? '+' : ''}${x.toFixed(digits)}` }
function prob(x: number | null | undefined) {
  if (x == null) return '—'
  if (x < 0.001) return '<0.001'
  return x.toFixed(3)
}

function chartGeometry(points: Point[], width: number, height: number) {
  if (!points.length) return { d: '', zeroY: height / 2, min: 0, max: 0, yFor: (_v: number) => height / 2 }
  const vals = points.map(p => p.value)
  let min = Math.min(...vals), max = Math.max(...vals)
  if (min === max) { min -= 1; max += 1 }
  const pad = (max - min) * 0.08
  min -= pad; max += pad
  const span = max - min
  const yFor = (v: number) => height - ((v - min) / span) * height
  const d = points.map((p, i) => {
    const x = (i / Math.max(points.length - 1, 1)) * width
    const y = yFor(p.value)
    return `${i ? 'L' : 'M'} ${x.toFixed(2)} ${y.toFixed(2)}`
  }).join(' ')
  return { d, zeroY: yFor(0), min, max, yFor }
}

function sliceByPreset<T extends { date: string }>(rows: T[], preset: string, anchor?: string) {
  if (preset === 'all' || !rows.length) return rows
  const days = preset === '3y' ? 365 * 3 : preset === '1y' ? 365 : 90
  const end = Date.parse(anchor ?? rows.at(-1)!.date)
  const cutoff = end - days * 86_400_000
  return rows.filter(row => Date.parse(row.date) >= cutoff)
}

function SparkChart({ points, kind = 'equity' }: { points: Point[]; kind?: 'equity' | 'drawdown' | 'reliability' }) {
  const w = 920, h = 300
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const { d, zeroY, min, max, yFor } = chartGeometry(points, w, h)
  const last = points.at(-1)?.value ?? 0
  const fmt = (v: number) => kind === 'equity' ? `${v.toFixed(2)}×` : kind === 'drawdown' ? pct(v, 0) : v.toFixed(1)
  const active = activeIndex == null ? null : points[activeIndex]
  const activeX = activeIndex == null ? 0 : (activeIndex / Math.max(points.length - 1, 1)) * w
  const activeY = active ? yFor(active.value) : 0
  const move = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!points.length) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / Math.max(rect.width, 1)))
    setActiveIndex(Math.round(ratio * Math.max(points.length - 1, 0)))
  }
  return <div className="chart-wrap">
    <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`${kind} chart`} onPointerMove={move} onPointerDown={move} onMouseLeave={()=>setActiveIndex(null)}>
      {[0.2,0.4,0.6,0.8].map(y => <line key={y} x1="0" x2={w} y1={h*y} y2={h*y} className="grid" />)}
      {kind === 'reliability' && zeroY >= 0 && zeroY <= h && <line x1="0" x2={w} y1={zeroY} y2={zeroY} className="zero" />}
      <path d={d} className={`line ${kind}`} fill="none" />
      {active && <g className="chart-focus">
        <line x1={activeX} x2={activeX} y1="0" y2={h} />
        <circle cx={activeX} cy={activeY} r="5" />
      </g>}
    </svg>
    <div className="y-label top">{fmt(max)}</div>
    <div className="y-label bottom">{fmt(min)}</div>
    <div className="chart-axis"><span>{points[0]?.date ?? ''}</span><span>{points.at(-1)?.date ?? ''}</span></div>
    <div className={`chart-last ${kind}`}>{kind === 'equity' ? `${last.toFixed(2)}×` : kind === 'drawdown' ? pct(last) : num(last)}</div>
    {active && <div className="chart-tooltip" style={{left:`${Math.min(82, Math.max(4, (activeX / w) * 100))}%`}}><strong>{active.date}</strong><span>{fmt(active.value)}</span></div>}
  </div>
}

function MetricCard({ label, value, tone = 'neutral', sub }: { label: string; value: string; tone?: 'green'|'red'|'neutral'|'violet'|'amber'; sub?: string }) {
  return <div className="metric-card">
    <div className="metric-label">{label}</div>
    <div className={`metric-value ${tone}`}>{value}</div>
    {sub && <div className="metric-sub">{sub}</div>}
  </div>
}

function TradeGrid({ run, trades, selectedTrade, onSelectTrade }: { run: Run; trades: Run['trades']; selectedTrade: Run['trades'][number] | null; onSelectTrade: (trade: Run['trades'][number]) => void }) {
  const recent = trades.slice(-180)
  const hit = recent.filter(t=>t.outcome==='win').length / Math.max(recent.filter(t=>t.outcome!=='flat').length,1)
  return <div>
    <div className="streak-row">
      <MetricCard label="LONGEST WIN STREAK" value={`${run.metrics.longest_win_streak} sessions`} tone="green" />
      <MetricCard label="LONGEST LOSS STREAK" value={`${run.metrics.longest_loss_streak} sessions`} tone="red" />
      <MetricCard label="RECENT HIT RATE" value={pct(hit, 0)} sub={`last ${recent.length} visible sessions`} />
    </div>
    <div className="trade-grid" aria-label="Clickable trade outcome grid">
      {recent.map((t,i) => <button type="button" key={`${t.date}-${i}`} className={`trade-cell ${t.outcome} ${selectedTrade?.date===t.date ? 'selected' : ''}`} title={`${t.date} • ${t.direction} • ${pct(t.return,2)}`} aria-label={`${t.date}, ${t.direction}, ${t.outcome}, ${pct(t.return,2)}`} onClick={()=>onSelectTrade(t)} />)}
    </div>
    <div className="trade-detail" aria-live="polite">
      {selectedTrade ? <><strong>{selectedTrade.date}</strong><span>{selectedTrade.direction.toUpperCase()}</span><span className={selectedTrade.return>=0?'green':'red'}>{pct(selectedTrade.return,2)}</span><small>{selectedTrade.outcome}</small></> : <><MousePointer2 size={14}/><span>Click any square to inspect that session.</span></>}
    </div>
  </div>
}

function RegimeTable({ run }: { run: Run }) {
  return <div className="regime-grid">
    {run.regime_performance.map(r => <div className="regime-card" key={r.regime}>
      <div className="regime-title">{r.regime.toUpperCase()} VOL</div>
      <div className={`regime-return ${r.return >= 0 ? 'green' : 'red'}`}>{pct(r.return)}</div>
      <div className="regime-meta"><span>Sharpe {num(r.sharpe)}</span><span>Hit {pct(r.hit_rate,0)}</span><span>n={r.observations}</span></div>
      <div className="regime-bar"><i style={{width: `${Math.min(100, Math.max(8, Math.abs(r.return)*100))}%`}} /></div>
    </div>)}
  </div>
}

function Leaderboard({ runs, selectedSignal, onSelect }: { runs: Run[]; selectedSignal: string; onSelect: (signal: string) => void }) {
  const ordered = [...runs].sort((a,b) => b.metrics.sharpe - a.metrics.sharpe)
  return <div className="leaderboard">
    {ordered.map((r, i) => <button type="button" className={`leader-row ${r.signal===selectedSignal ? 'selected' : ''}`} key={r.signal} onClick={()=>onSelect(r.signal)}>
      <span className="rank">0{i+1}</span>
      <span className="leader-name">{signalLabels[r.signal] ?? r.signal}</span>
      <span className={r.metrics.total_return >= 0 ? 'green' : 'red'}>{pct(r.metrics.total_return)}</span>
      <span className="leader-sharpe">S {num(r.metrics.sharpe)}</span>
      <span className="leader-q">q {prob(r.robustness.fdr_q)}</span>
    </button>)}
  </div>
}

function FoldStrip({ run }: { run: Run }) {
  if (!run.folds.length) return <div className="empty-folds">Full-sample optimisation selected lookback <strong>{run.selected_lookback ?? '—'}d</strong>.</div>
  return <div>
    <div className="fold-strip">
      {run.folds.map((f, i) => <div
        key={`${f.test_start}-${i}`}
        className={`fold-cell lb-${f.lookback}`}
        title={`${f.test_start} → ${f.test_end} • ${f.lookback}d lookback • train Sharpe ${f.train_sharpe.toFixed(2)}`}
      ><span>{f.lookback}</span></div>)}
    </div>
    <div className="fold-caption"><span>{run.folds[0]?.test_start}</span><span>selected lookback by unseen test block</span><span>{run.folds.at(-1)?.test_end}</span></div>
  </div>
}

function EvidencePanel({ run }: { run: Run }) {
  const r = run.robustness
  const grade = r.evidence_grade.toUpperCase()
  const gradeTone = r.evidence_grade === 'strong' ? 'green' : r.evidence_grade === 'promising' ? 'violet' : r.evidence_grade === 'no evidence' ? 'red' : 'amber'
  return <div className="evidence-grid">
    <MetricCard label="EVIDENCE GRADE" value={grade} tone={gradeTone} sub="heuristic summary of OOS evidence" />
    <MetricCard label="HAC T-STAT" value={num(r.hac_t_stat)} sub="Newey–West, 7 lags" />
    <MetricCard label="RAW P-VALUE" value={prob(r.p_value)} />
    <MetricCard label="FDR Q-VALUE" value={prob(r.fdr_q)} sub="BH across four signals" />
    <MetricCard label="SHARPE 95% CI" value={`${num(r.sharpe_ci_low)} → ${num(r.sharpe_ci_high)}`} sub="7-day moving-block bootstrap" />
    <MetricCard label="REALITY-CHECK P" value={prob(run.selection_bias?.reality_check_p)} sub={`${run.selection_bias?.trials ?? 0} fixed specifications`} />
    <MetricCard label="EXPOSURE" value={pct(run.metrics.exposure,0)} sub={`benchmark ${pct(r.benchmark_return)}`} />
  </div>
}


function DeploymentGatePanel({ run }: { run: Run }) {
  const gate = run.deployment_gate ?? { status: 'not_available', passed: 0, total: 0, criteria: [] }
  const tone = gate.status === 'pass' ? 'green' : gate.status === 'watch' ? 'amber' : gate.status === 'not_applicable' ? 'neutral' : 'red'
  const breakEven = run.break_even_fee_bps == null ? '>100 bps' : `${run.break_even_fee_bps.toFixed(1)} bps`
  return <div className="gate-layout">
    <div className={`gate-score ${tone}`}>
      <span className="eyebrow">DEPLOYMENT GATE</span>
      <strong>{gate.status.replace('_',' ').toUpperCase()}</strong>
      <div>{gate.total ? `${gate.passed}/${gate.total} checks cleared` : 'Comparator view only'}</div>
      <small>break-even fee {breakEven}</small>
    </div>
    <div className="gate-criteria">
      {gate.criteria.map(c => <div className={`gate-chip ${c.pass ? 'pass' : 'fail'}`} key={c.name}>
        <span>{c.pass ? '✓' : '×'}</span>{c.label}
      </div>)}
    </div>
  </div>
}

function YearConsistency({ run, onSelectYear }: { run: Run; onSelectYear: (year: number) => void }) {
  if (!run.yearly_performance?.length) return <div className="empty-folds">No yearly breakdown available.</div>
  return <div className="year-grid">
    {run.yearly_performance.map(y => <button type="button" className={`year-card ${y.return >= 0 ? 'up' : 'down'}`} key={y.year} onClick={()=>onSelectYear(y.year)} title={`Focus charts on ${y.year}`}>
      <div className="year-head"><strong>{y.year}</strong><span>{pct(y.return)}</span></div>
      <div className="year-meta"><span>Sharpe {num(y.sharpe)}</span><span>DD {pct(y.max_drawdown,0)}</span><span>{y.active_sessions} active</span></div>
    </button>)}
  </div>
}

function EdgeDecay({ run }: { run: Run }) {
  const vals = run.edge_decay.map(x=>x.mean_edge_bps ?? 0)
  const maxAbs = Math.max(1, ...vals.map(Math.abs))
  return <div className="bar-stack">
    {run.edge_decay.map(row => {
      const val = row.mean_edge_bps ?? 0
      return <div className="bar-row" key={row.horizon}>
        <span className="bar-label">{row.horizon}d</span>
        <div className="bar-track"><i className={val>=0?'positive':'negative'} style={{width:`${Math.max(3, Math.abs(val)/maxAbs*100)}%`}} /></div>
        <span className={val>=0?'green':'red'}>{val>=0?'+':''}{val.toFixed(1)} bps</span>
        <span className="bar-meta">hit {row.hit_rate==null?'—':pct(row.hit_rate,0)} · n={row.observations}</span>
      </div>
    })}
  </div>
}

function CostStress({ run }: { run: Run }) {
  const vals = run.cost_stress.map(x=>x.total_return)
  const maxAbs = Math.max(.01, ...vals.map(Math.abs))
  return <div className="bar-stack">
    {run.cost_stress.map(row => <div className="bar-row" key={row.fee_bps}>
      <span className="bar-label">{row.fee_bps.toFixed(0)} bps</span>
      <div className="bar-track"><i className={row.total_return>=0?'positive':'negative'} style={{width:`${Math.max(3, Math.abs(row.total_return)/maxAbs*100)}%`}} /></div>
      <span className={row.total_return>=0?'green':'red'}>{pct(row.total_return)}</span>
      <span className="bar-meta">Sharpe {num(row.sharpe)}</span>
    </div>)}
  </div>
}


function DelayStress({ run }: { run: Run }) {
  const vals = run.execution_delay_stress?.map(x=>x.total_return) ?? []
  const maxAbs = Math.max(.01, ...vals.map(Math.abs))
  return <div className="bar-stack">
    {(run.execution_delay_stress ?? []).map(row => <div className="bar-row" key={row.delay_days}>
      <span className="bar-label">t+{row.delay_days}</span>
      <div className="bar-track"><i className={row.total_return>=0?'positive':'negative'} style={{width:`${Math.max(3, Math.abs(row.total_return)/maxAbs*100)}%`}} /></div>
      <span className={row.total_return>=0?'green':'red'}>{pct(row.total_return)}</span>
      <span className="bar-meta">Sharpe {num(row.sharpe)}</span>
    </div>)}
  </div>
}

function ParameterSensitivityPanel({ run }: { run: Run }) {
  const rows = run.parameter_sensitivity?.rows ?? []
  const vals = rows.map(x=>x.sharpe)
  const maxAbs = Math.max(.01, ...vals.map(Math.abs))
  return <div>
    <div className="bar-stack">
      {rows.map(row => <div className="bar-row" key={row.lookback}>
        <span className="bar-label">{row.lookback}d</span>
        <div className="bar-track"><i className={row.sharpe>=0?'positive':'negative'} style={{width:`${Math.max(3, Math.abs(row.sharpe)/maxAbs*100)}%`}} /></div>
        <span className={row.sharpe>=0?'green':'red'}>S {num(row.sharpe)}</span>
        <span className="bar-meta">{pct(row.total_return)}</span>
      </div>)}
    </div>
    <div className="chart-footnote">Ex-post sensitivity only — not used for inference. Plateau score {pct(run.parameter_sensitivity?.plateau_score ?? 0,0)}; positive across {pct(run.parameter_sensitivity?.positive_parameter_share ?? 0,0)} of declared lookbacks.</div>
  </div>
}

function FragilityPanel({ run }: { run: Run }) {
  const c = run.return_concentration
  const s = run.selection_bias
  const rcTone = s?.reality_check_p != null && s.reality_check_p < .10 ? 'green' : 'red'
  const strippedTone = c?.return_without_best_sessions >= 0 ? 'green' : 'red'
  return <div className="evidence-grid fragility-grid">
    <MetricCard label="SEARCH-SPACE REALITY CHECK" value={prob(s?.reality_check_p)} tone={rcTone} sub={`${s?.trials ?? 0} signal/lookback trials`} />
    <MetricCard label="BEST FIXED SPEC" value={(s?.best_specification ?? '—').replace(':',' · ')} sub="best ex-post fixed rule in declared search" />
    <MetricCard label="TOP-10 PROFIT SHARE" value={c?.top_profit_share == null ? '—' : pct(c.top_profit_share,0)} sub="share of gross positive P&L" />
    <MetricCard label="WITHOUT BEST 10 SESSIONS" value={c ? pct(c.return_without_best_sessions) : '—'} tone={strippedTone} sub="same OOS path, best active sessions zeroed" />
    <MetricCard label="PARAMETER PLATEAU" value={pct(run.parameter_sensitivity?.plateau_score ?? 0,0)} sub="share retaining ≥ 50% of best Sharpe" />
    <MetricCard label="ACTIVE SESSIONS" value={`${c?.active_sessions ?? 0}`} sub="concentration denominator" />
  </div>
}


function CrossAssetPanel({ run, onSelectAsset }: { run: Run; onSelectAsset: (asset: string) => void }) {
  const c = run.cross_asset
  const h = c?.holdout
  if (!c) return <div className="empty-folds">Cross-asset diagnostics unavailable.</div>
  return <div>
    <div className="cross-asset-grid">
      {(c.asset_rows ?? []).map(row => <button type="button" className={`cross-card ${row.positive ? 'up' : 'down'}`} key={row.symbol} onClick={()=>onSelectAsset(row.symbol)}>
        <div className="cross-head"><strong>{row.symbol.replace('USDT','')}</strong><span className={row.positive?'green':'red'}>{pct(row.total_return)}</span></div>
        <div className="year-meta"><span>Sharpe {num(row.sharpe)}</span><span>q {prob(row.fdr_q)}</span></div>
      </button>)}
      <div className={`cross-card holdout ${h?.available && h.positive ? 'up' : 'down'}`}>
        <div className="cross-head"><strong>ASSET HOLDOUT</strong><span className={h?.available && h.positive?'green':'red'}>{h?.available && h.total_return != null ? pct(h.total_return) : '—'}</span></div>
        <div className="year-meta"><span>{h?.available ? `${h.chosen_lookback}d chosen on ${(h.donors ?? []).map(x=>x.replace('USDT','')).join(' + ')}` : (h?.reason ?? 'unavailable')}</span><span>{h?.available ? `Sharpe ${num(h.sharpe)}` : ''}</span></div>
      </div>
    </div>
    <div className="chart-footnote">Replication breadth: {pct(c.positive_share ?? 0,0)} positive across displayed assets · median OOS Sharpe {num(c.median_sharpe)}. Click an asset card to switch the whole dashboard. The held-out test selects the lookback on the other assets only.</div>
  </div>
}

type TabKey = 'overview' | 'evidence' | 'robustness' | 'validation' | 'trades' | 'lab'

const tabMeta: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'overview', label: 'Overview', icon: <LayoutDashboard size={17}/> },
  { key: 'evidence', label: 'Evidence', icon: <BadgeCheck size={17}/> },
  { key: 'robustness', label: 'Robustness', icon: <SlidersHorizontal size={17}/> },
  { key: 'validation', label: 'Validation', icon: <Globe2 size={17}/> },
  { key: 'trades', label: 'Trades', icon: <Grid3X3 size={17}/> },
  { key: 'lab', label: 'Live Lab', icon: <UploadCloud size={17}/> },
]

function runScore(r: Run) {
  const gateShare = r.deployment_gate.total ? r.deployment_gate.passed / r.deployment_gate.total : 0
  const evidenceBoost = r.robustness.evidence_grade === 'strong' ? 2 : r.robustness.evidence_grade === 'promising' ? 1 : 0
  const qBoost = r.robustness.fdr_q != null && r.robustness.fdr_q < 0.10 ? 1 : 0
  return gateShare * 100 + evidenceBoost * 8 + qBoost * 5 + r.metrics.sharpe * 3 + r.metrics.total_return
}

function bestRun(runs: Run[]) {
  return [...runs].sort((a,b) => runScore(b) - runScore(a))[0] ?? null
}

function App() {
  const query = useMemo(() => new URLSearchParams(location.search), [])
  const costParam = query.get('cost')
  const queryFee = costParam == null ? null : Number(costParam)
  const yearParam = query.get('year')
  const queryYear = yearParam == null ? null : Number(yearParam)
  const queryTab = query.get('tab') as TabKey | null
  const hasExplicitSelection = query.has('asset') || query.has('signal') || query.has('mode') || query.has('cost')

  const [payload, setPayload] = useState<Payload | null>(null)
  const [asset, setAsset] = useState(query.get('asset') ?? 'BTCUSDT')
  const [signal, setSignal] = useState(query.get('signal') ?? 'momentum')
  const [mode, setMode] = useState(query.get('mode') ?? 'walk_forward')
  const [fee, setFee] = useState(queryFee != null && Number.isFinite(queryFee) ? queryFee : 10)
  const [activeTab, setActiveTab] = useState<TabKey>(tabMeta.some(t=>t.key===queryTab) ? queryTab! : 'overview')
  const [windowPreset, setWindowPreset] = useState(['3y','1y','90d'].includes(query.get('view') ?? '') ? (query.get('view') as string) : 'all')
  const [focusedYear, setFocusedYear] = useState<number | null>(queryYear != null && Number.isInteger(queryYear) && queryYear > 2000 ? queryYear : null)
  const [selectedTrade, setSelectedTrade] = useState<Run['trades'][number] | null>(null)

  useEffect(() => {
    fetch('./results.json').then(r => {
      if (!r.ok) throw new Error('no empirical payload')
      return r.json()
    }).then(setPayload).catch(() => fetch('./demo-results.json').then(r=>r.json()).then(setPayload))
  }, [])

  const allRuns = payload?.runs ?? []
  const assets: string[] = useMemo(() => [...new Set<string>(allRuns.map(r=>r.symbol))], [allRuns])
  const modes: string[] = useMemo(() => [...new Set<string>(allRuns.filter(r=>r.symbol===asset).map(r=>r.mode))], [allRuns,asset])
  const fees: number[] = useMemo(() => [...new Set<number>(allRuns.filter(r=>r.symbol===asset && r.mode===mode).map(r=>r.fee_bps))].sort((a,b)=>a-b), [allRuns,asset,mode])
  const signals: string[] = useMemo(() => [...new Set<string>(allRuns.filter(r=>r.symbol===asset && r.mode===mode && r.fee_bps===fee).map(r=>r.signal))], [allRuns,asset,mode,fee])

  useEffect(() => {
    if (!payload || !payload.runs.length || hasExplicitSelection) return
    const preferredAsset = payload.runs.some(r=>r.symbol==='BTCUSDT') ? 'BTCUSDT' : payload.runs[0].symbol
    const preferredMode = payload.runs.some(r=>r.symbol===preferredAsset && r.mode==='walk_forward') ? 'walk_forward' : payload.runs.find(r=>r.symbol===preferredAsset)!.mode
    const availableFees: number[] = [...new Set<number>(payload.runs.filter(r=>r.symbol===preferredAsset && r.mode===preferredMode).map(r=>r.fee_bps))]
    const preferredFee = availableFees.includes(10) ? 10 : [...availableFees].sort((a,b)=>Math.abs(a-10)-Math.abs(b-10))[0]
    const recommended = bestRun(payload.runs.filter(r=>r.symbol===preferredAsset && r.mode===preferredMode && r.fee_bps===preferredFee))
    setAsset(preferredAsset)
    setMode(preferredMode)
    setFee(preferredFee)
    if (recommended) setSignal(recommended.signal)
  }, [payload, hasExplicitSelection])

  useEffect(() => {
    if (!payload || !allRuns.length) return
    if (!assets.includes(asset)) setAsset(assets[0])
  }, [payload, allRuns, assets, asset])

  useEffect(() => {
    if (!payload || !modes.length) return
    if (!modes.includes(mode)) setMode(modes.includes('walk_forward') ? 'walk_forward' : modes[0])
  }, [payload,modes,mode])

  useEffect(() => {
    if (!payload || !fees.length) return
    if (!fees.includes(fee)) setFee(fees.includes(10) ? 10 : [...fees].sort((a,b)=>Math.abs(a-10)-Math.abs(b-10))[0])
  }, [payload,fees,fee])

  useEffect(() => {
    if (!payload || !signals.length) return
    if (!signals.includes(signal)) {
      const recommended = bestRun(allRuns.filter(r=>r.symbol===asset && r.mode===mode && r.fee_bps===fee))
      if (recommended) setSignal(recommended.signal)
    }
  }, [payload,signals,signal,allRuns,asset,mode,fee])

  const run = useMemo(() => allRuns.find(r => r.symbol===asset && r.signal===signal && r.mode===mode && r.fee_bps===fee) ?? null, [allRuns,asset,signal,mode,fee])
  const peers = useMemo(() => allRuns.filter(r => r.symbol===asset && r.mode===mode && r.fee_bps===fee), [allRuns,asset,mode,fee])
  const counterpart = useMemo(() => allRuns.find(r => r.symbol===asset && r.signal===signal && r.mode===(mode==='walk_forward'?'in_sample':'walk_forward') && r.fee_bps===fee), [allRuns,asset,signal,mode,fee])

  useEffect(() => { setSelectedTrade(null) }, [asset, signal, mode, fee, windowPreset, focusedYear])

  useEffect(() => {
    if (!payload || !run) return
    const q = new URLSearchParams()
    q.set('asset', asset)
    q.set('signal', signal)
    q.set('mode', mode)
    q.set('cost', String(fee))
    if (activeTab !== 'overview') q.set('tab', activeTab)
    if (windowPreset !== 'all') q.set('view', windowPreset)
    if (focusedYear != null) q.set('year', String(focusedYear))
    history.replaceState(null, '', `${location.pathname}${q.toString() ? `?${q}` : ''}${location.hash}`)
  }, [payload,run,asset,signal,mode,fee,activeTab,windowPreset,focusedYear])

  if (!payload) return <div className="loading"><div className="loading-orb"/>Loading SignalLab…</div>
  if (!run) return <div className="loading">Resolving experiment…</div>

  const windowed = <T extends {date:string},>(rows: T[]) => {
    if (focusedYear != null) return rows.filter(row => Number(row.date.slice(0,4)) === focusedYear)
    return sliceByPreset(rows, windowPreset, run.end_date)
  }
  const visibleEquity: Point[] = windowed<Point>(run.equity)
  const visibleDrawdown: Point[] = windowed<Point>(run.drawdown)
  const visibleReliability: Point[] = windowed<Point>(run.rolling_reliability)
  const visibleTrades: Run['trades'] = windowed<Run['trades'][number]>(run.trades)

  const m = run.metrics
  const profitable = m.total_return >= 0
  const isDemo = payload.data_source?.kind === 'synthetic'
  const audit = payload.data_audit?.[asset]
  const comparisonLabel = mode === 'walk_forward' ? 'WF − IS Sharpe' : 'IS − WF Sharpe'
  const validationGap = counterpart ? m.sharpe - counterpart.metrics.sharpe : null
  const stateTone = run.signal_state.label === 'strong' ? 'green' : run.signal_state.label === 'broken' || run.signal_state.label === 'decaying' ? 'red' : 'violet'
  const gateTone = run.deployment_gate.status.toLowerCase().includes('pass') ? 'green' : run.deployment_gate.passed >= Math.ceil(run.deployment_gate.total/2) ? 'amber' : 'red'
  const cleanAsset = asset.replace('USDT','')

  const chartToolbar = <section className="view-toolbar" aria-label="Chart view controls">
    <div className="view-label"><CalendarDays size={15}/><span>Chart window</span></div>
    <div className="preset-group">
      {[['all','All'],['3y','3Y'],['1y','1Y'],['90d','90D']].map(([key,label]) => <button type="button" key={key} className={windowPreset===key && focusedYear==null ? 'active' : ''} onClick={()=>{setWindowPreset(key);setFocusedYear(null)}}>{label}</button>)}
    </div>
    {focusedYear != null && <button type="button" className="year-focus active" onClick={()=>setFocusedYear(null)}>{focusedYear} ×</button>}
    <button type="button" className="reset-view" onClick={()=>{setWindowPreset('all');setFocusedYear(null);setSelectedTrade(null)}}><RotateCcw size={14}/> Reset</button>
    <span className="interaction-hint"><MousePointer2 size={14}/> hover charts · click rows and cards</span>
  </section>

  return <main className="shell">
    <header className="topbar">
      <div className="brand"><div className="brandmark"><BrainCircuit size={22}/></div><div><strong>SignalLab</strong><span>SYSTEMATIC SIGNAL RESEARCH</span></div></div>
      <div className="header-right">
        <div className={`source-badge ${isDemo ? 'demo' : 'real'}`}><FlaskConical size={15}/>{payload.data_source?.label ?? 'Local data'}</div>
        {audit && <div className={`quality-badge ${audit.clean ? 'clean' : 'warn'}`}><ShieldCheck size={15}/>{audit.clean ? 'DATA AUDIT CLEAN' : 'DATA AUDIT FLAGGED'}</div>}
      </div>
    </header>

    {isDemo && <section className="demo-banner"><Sparkles size={16}/><strong>Offline demo.</strong> {payload.data_source.claim_status}. The interface is real; displayed P&amp;L is illustrative until the public-data build runs.</section>}

    <section className="intro-hero">
      <div className="intro-copy">
        <span className="intro-kicker">OUT-OF-SAMPLE RESEARCH CONSOLE</span>
        <h1>Stress-test the signal,<br/><span>not the story.</span></h1>
        <p>Explore predictive signals across markets, then challenge them with walk-forward validation, execution costs, parameter perturbations and cross-asset tests.</p>
      </div>
      <div className="experiment-summary">
        <div className="summary-top"><span>CURRENT EXPERIMENT</span><strong>{cleanAsset} · {signalLabels[signal] ?? signal}</strong></div>
        <div className="summary-number"><span className={profitable?'green':'red'}>{pct(m.total_return)}</span><small>{mode==='walk_forward'?'walk-forward':'in-sample'} total return at {fee} bps</small></div>
        <div className="summary-meta"><span>Sharpe <b>{num(m.sharpe)}</b></span><span>Gate <b className={gateTone}>{run.deployment_gate.passed}/{run.deployment_gate.total}</b></span><span>Evidence <b>{run.robustness.evidence_grade}</b></span></div>
      </div>
    </section>

    <section className="control-dock">
      <label><span>Asset</span><select value={asset} onChange={e=>{setAsset(e.target.value);setFocusedYear(null)}}>{assets.map(x=><option key={x} value={x}>{x.replace('USDT','')}</option>)}</select></label>
      <label><span>Signal</span><select value={signal} onChange={e=>{setSignal(e.target.value);setFocusedYear(null)}}>{signals.map(k=><option key={k} value={k}>{signalLabels[k] ?? k}</option>)}</select></label>
      <label><span>Validation</span><select value={mode} onChange={e=>setMode(e.target.value)}>{modes.map(x=><option key={x} value={x}>{x==='walk_forward'?'Walk-forward':'In-sample optimised'}</option>)}</select></label>
      <label><span>Costs</span><select value={fee} onChange={e=>setFee(Number(e.target.value))}>{fees.map(x=><option key={x} value={x}>{x} bps</option>)}</select></label>
      <div className="evaluation-range"><span>Evaluation window</span><strong>{run.start_date} → {run.end_date}</strong></div>
    </section>

    <nav className="tabbar" aria-label="SignalLab sections">
      {tabMeta.map(t=><button type="button" key={t.key} className={activeTab===t.key?'active':''} onClick={()=>setActiveTab(t.key)}>{t.icon}<span>{t.label}</span></button>)}
    </nav>

    {activeTab === 'overview' && <div className="tab-page overview-page">
      {chartToolbar}
      <section className="overview-hero">
        <div className="panel chart-panel hero-chart">
          <div className="panel-heading"><div><span className="eyebrow">STRATEGY PERFORMANCE</span><h2>Equity curve</h2></div><div className={`status ${profitable?'positive':'negative'}`}>{profitable?<ArrowUpRight size={18}/>:<ArrowDownRight size={18}/>} {pct(m.total_return)}</div></div>
          <SparkChart points={visibleEquity}/>
        </div>
        <aside className="overview-rail">
          <div className={`decision-card ${gateTone}`}>
            <span>DEPLOYMENT GATE</span>
            <strong>{run.deployment_gate.status.toUpperCase()}</strong>
            <div>{run.deployment_gate.passed}/{run.deployment_gate.total} checks cleared</div>
            <small>Break-even fee {run.break_even_fee_bps == null ? '—' : `${run.break_even_fee_bps.toFixed(1)} bps`}</small>
          </div>
          <div className="state-card">
            <span>SIGNAL STATE</span><strong className={stateTone}>{run.signal_state.label.toUpperCase()}</strong>
            <div><span>60d Sharpe</span><b>{num(run.signal_state.score)}</b></div>
            <div><span>30d change</span><b>{signed(run.signal_state.change_30d)}</b></div>
          </div>
        </aside>
      </section>

      <section className="kpi-strip">
        <MetricCard label="ANNUALISED RETURN" value={pct(m.annualized_return)} tone={m.annualized_return>=0?'green':'red'} />
        <MetricCard label="SHARPE" value={num(m.sharpe)} tone={m.sharpe>=1?'green':'neutral'} />
        <MetricCard label="MAX DRAWDOWN" value={pct(m.max_drawdown)} tone="red" />
        <MetricCard label="SORTINO" value={num(m.sortino)} />
        <MetricCard label="WIN RATE" value={pct(m.win_rate,0)} />
        <MetricCard label="TURNOVER" value={`${m.turnover.toFixed(0)}×`} />
      </section>

      <section className="two-col overview-bottom">
        <div className="panel section-panel no-margin">
          <div className="panel-heading"><div><span className="eyebrow">CROSS-SIGNAL VIEW</span><h2>Signal leaderboard</h2></div><Layers3 size={19}/></div>
          <Leaderboard runs={peers} selectedSignal={signal} onSelect={s=>{setSignal(s);setFocusedYear(null)}}/>
        </div>
        <div className="panel section-panel no-margin">
          <div className="panel-heading"><div><span className="eyebrow">OUT-OF-SAMPLE EVIDENCE</span><h2>What survives first inspection?</h2></div><Microscope size={19}/></div>
          <EvidencePanel run={run}/>
        </div>
      </section>
    </div>}

    {activeTab === 'evidence' && <div className="tab-page">
      <div className="page-heading"><span>EVIDENCE</span><h2>Separate performance from statistical evidence.</h2><p>The gate is deliberately difficult to clear. A positive equity curve is not enough.</p></div>
      <section className="panel section-panel evidence-panel"><div className="panel-heading"><div><span className="eyebrow">STATISTICAL ROBUSTNESS</span><h2>Out-of-sample evidence</h2></div><Microscope size={19}/></div><EvidencePanel run={run}/></section>
      <section className="panel section-panel gate-panel"><div className="panel-heading"><div><span className="eyebrow">RESEARCH DECISION</span><h2>Would this survive a deployment review?</h2></div><ShieldCheck size={19}/></div><DeploymentGatePanel run={run}/></section>
      <section className="two-col">
        <div className="panel section-panel no-margin"><div className="panel-heading"><div><span className="eyebrow">MODEL SELECTION</span><h2>{mode==='walk_forward'?'Walk-forward lookback path':'Full-sample selection'}</h2></div><span className="mini-note">stability {run.parameter_stability.stability_score==null?'—':pct(run.parameter_stability.stability_score,0)}</span></div><FoldStrip run={run}/></div>
        <div className="panel"><div className="panel-heading"><div><span className="eyebrow">SIGNAL RELIABILITY</span><h2>Rolling 60-day Sharpe</h2></div><span className="mini-note">diagnostic, not forecast</span></div><SparkChart points={visibleReliability} kind="reliability"/></div>
      </section>
      {chartToolbar}
      <section className="panel"><div className="panel-heading"><div><span className="eyebrow">RISK PATH</span><h2>Drawdown through the evaluation window</h2></div><Activity size={19}/></div><SparkChart points={visibleDrawdown} kind="drawdown"/></section>
    </div>}

    {activeTab === 'robustness' && <div className="tab-page">
      <div className="page-heading"><span>ROBUSTNESS</span><h2>Try to break the result.</h2><p>Stress the same signal under costs, delays, alternate horizons and neighbouring parameter choices.</p></div>
      <section className="two-col">
        <div className="panel section-panel no-margin"><div className="panel-heading"><div><span className="eyebrow">FRICTION ROBUSTNESS</span><h2>Transaction-cost stress</h2></div><span className="mini-note">fixed signal path</span></div><CostStress run={run}/><div className="chart-footnote">The selected positions are repriced at progressively higher execution costs without re-optimising.</div></div>
        <div className="panel section-panel no-margin"><div className="panel-heading"><div><span className="eyebrow">IMPLEMENTATION ROBUSTNESS</span><h2>Execution-delay stress</h2></div><span className="mini-note">t+1 → t+5</span></div><DelayStress run={run}/><div className="chart-footnote">Fast collapse under a short execution delay is a warning that the apparent edge is timing-fragile.</div></div>
      </section>
      <section className="two-col">
        <div className="panel section-panel no-margin"><div className="panel-heading"><div><span className="eyebrow">PARAMETER ROBUSTNESS</span><h2>Lookback sensitivity</h2></div><span className="mini-note">5 pre-declared values</span></div><ParameterSensitivityPanel run={run}/></div>
        <div className="panel section-panel no-margin"><div className="panel-heading"><div><span className="eyebrow">SIGNAL DECAY</span><h2>Signed forward return by horizon</h2></div><BarChart3 size={19}/></div><EdgeDecay run={run}/><div className="chart-footnote">Exploratory horizon diagnostic; overlapping multi-day outcomes are not used in the primary HAC test.</div></div>
      </section>
      <section className="panel section-panel fragility-panel"><div className="panel-heading"><div><span className="eyebrow">SELECTION & CONCENTRATION RISK</span><h2>Lucky specification, or repeatable edge?</h2></div><Microscope size={19}/></div><FragilityPanel run={run}/><div className="chart-footnote">Reality-check and concentration diagnostics test whether the headline result is dominated by search or a few exceptional sessions.</div></section>
    </div>}

    {activeTab === 'validation' && <div className="tab-page">
      <div className="page-heading"><span>VALIDATION</span><h2>Ask whether the signal travels.</h2><p>Replication across markets, calendar years and volatility regimes is shown separately from the headline backtest.</p></div>
      <section className="panel section-panel"><div className="panel-heading"><div><span className="eyebrow">CROSS-ASSET VALIDATION</span><h2>Does the signal travel beyond one market?</h2></div><span className="mini-note">replication + held-out transfer</span></div><CrossAssetPanel run={run} onSelectAsset={a=>{setAsset(a);setFocusedYear(null);setActiveTab('overview')}}/></section>
      <section className="panel section-panel"><div className="panel-heading"><div><span className="eyebrow">TEMPORAL CONSISTENCY</span><h2>Year-by-year out-of-sample behaviour</h2></div><span className="mini-note">click a year to inspect</span></div><YearConsistency run={run} onSelectYear={y=>{setFocusedYear(y);setWindowPreset('all');setActiveTab('overview')}}/></section>
      <section className="panel section-panel"><div className="panel-heading"><div><span className="eyebrow">CONDITIONAL PERFORMANCE</span><h2>Performance by volatility regime</h2></div><span className="mini-note">regime known before return</span></div><RegimeTable run={run}/></section>
    </div>}

    {activeTab === 'trades' && <div className="tab-page">
      <div className="page-heading"><span>TRADES</span><h2>Inspect the realised sequence.</h2><p>Use the outcome grid to see whether performance is broad-based or concentrated in a small number of sessions.</p></div>
      {chartToolbar}
      <section className="trade-kpi-row">
        <MetricCard label="LONGEST WIN STREAK" value={`${m.longest_win_streak} sessions`} tone="green"/>
        <MetricCard label="LONGEST LOSS STREAK" value={`${m.longest_loss_streak} sessions`} tone="red"/>
        <MetricCard label="EXPOSURE" value={pct(m.exposure,0)}/>
        <MetricCard label="TRADES" value={m.trades.toLocaleString()}/>
      </section>
      <section className="panel section-panel trades-panel"><div className="panel-heading"><div><span className="eyebrow">SEQUENCE DIAGNOSTICS</span><h2>Recent active sessions</h2></div><span className="legend"><i className="win"/>win <i className="loss"/>loss</span></div><TradeGrid run={run} trades={visibleTrades} selectedTrade={selectedTrade} onSelectTrade={setSelectedTrade}/></section>
      <section className="two-col"><div className="panel"><div className="panel-heading"><div><span className="eyebrow">EQUITY PATH</span><h2>Selected window</h2></div></div><SparkChart points={visibleEquity}/></div><div className="panel"><div className="panel-heading"><div><span className="eyebrow">DRAWDOWN</span><h2>Selected window</h2></div></div><SparkChart points={visibleDrawdown} kind="drawdown"/></div></section>
    </div>}

    {activeTab === 'lab' && <div className="tab-page lab-page">
      <div className="page-heading"><span>LIVE LAB</span><h2>Run a fresh experiment in your browser.</h2><p>Load daily OHLCV or raw Binance klines. The exploratory fixed-parameter test runs locally; your data does not leave the browser.</p></div>
      <LocalLab/>
      <section className="methodology-strip lab-method"><div><ShieldCheck size={16}/><span>Signal at <b>t</b> executes on <b>t+1</b></span></div><ChevronRight size={15}/><div><span>Main research view: 365d train → 90d unseen test</span></div><ChevronRight size={15}/><div><span>HAC + BH FDR + block bootstrap</span></div></section>
    </div>}

    <footer><span>SignalLab v1.2</span><span>Research software — not investment advice.</span></footer>
  </main>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
