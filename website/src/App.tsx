import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts'
import type { DecisionEvent, ArgDecision, ChatMessage, Scenario } from './types'

// ── API helpers ──────────────────────────────────────────────────────────────
const API = '/api'

async function apiPost(path: string, body: object) {
  const r = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return r.json()
}

async function apiGet(path: string) {
  const r = await fetch(API + path)
  return r.json()
}

// ── Confidence bar ───────────────────────────────────────────────────────────
function ConfBar({ value, label }: { value: number; label: string }) {
  const color =
    label === 'grounded' ? '#10b981' :
    label === 'not_grounded' ? '#ef4444' : '#f59e0b'
  return (
    <div className="conf-bar-track">
      <div className="conf-bar-fill" style={{ width: `${value * 100}%`, background: color }} />
    </div>
  )
}

// ── Outcome badge ────────────────────────────────────────────────────────────
function OutcomeBadge({ outcome }: { outcome: string }) {
  const cls =
    outcome === 'executed' ? 'badge-executed' :
    outcome === 'blocked' || outcome === 'block' ? 'badge-blocked' :
    outcome === 'clarify' ? 'badge-clarify' : 'badge-policy'
  const icon =
    outcome === 'executed' ? '✓' :
    outcome === 'blocked' || outcome === 'block' ? '✗' :
    outcome === 'clarify' ? '?' : '⊘'
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${cls}`}>
      {icon} {outcome}
    </span>
  )
}

// ── Decision card ────────────────────────────────────────────────────────────
function DecisionCard({ event }: { event: DecisionEvent }) {
  const [open, setOpen] = useState(false)
  const totalLat = event.arguments.reduce((s, a) => s + a.latency_ms, 0)

  return (
    <div className="glass rounded-xl p-4 animate-slide-in space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400">turn {event.turn}</span>
          <span className="text-sm font-semibold text-white font-mono">{event.tool}</span>
        </div>
        <div className="flex items-center gap-2">
          <OutcomeBadge outcome={event.outcome} />
          <span className="text-xs text-slate-500">{totalLat.toFixed(1)}ms</span>
        </div>
      </div>

      {/* Policy */}
      {event.policy.result !== 'allow' && (
        <div className="text-xs bg-blue-500/10 border border-blue-500/20 rounded-lg px-3 py-2 text-blue-300">
          Policy: <strong>{event.policy.rule}</strong> — {event.policy.detail}
        </div>
      )}

      {/* Args */}
      <div className="space-y-2">
        {event.arguments.map((arg) => (
          <div key={arg.name} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400 font-mono">{arg.name}=<span className="text-slate-200">{arg.value}</span></span>
              <div className="flex items-center gap-2">
                <span className={`font-semibold ${arg.label === 'grounded' ? 'text-emerald-400' : arg.label === 'not_grounded' ? 'text-red-400' : 'text-amber-400'}`}>
                  {arg.label}
                </span>
                <span className="text-slate-500">{(arg.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
            <ConfBar value={arg.confidence} label={arg.label} />
          </div>
        ))}
      </div>

      {/* Message */}
      {event.message_to_agent && (
        <p className="text-xs text-slate-400 italic">{event.message_to_agent}</p>
      )}

      {/* Details toggle */}
      <button
        id={`detail-toggle-${event.event_id}`}
        onClick={() => setOpen(o => !o)}
        className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
      >
        {open ? '▲ hide raw event' : '▼ show raw event'}
      </button>
      {open && (
        <pre className="text-xs font-mono bg-surface-900 rounded-lg p-3 overflow-auto max-h-48 text-slate-400">
          {JSON.stringify(event, null, 2)}
        </pre>
      )}
    </div>
  )
}

// ── Chat panel ───────────────────────────────────────────────────────────────
function ChatPanel({ guardEnabled, sessionId }: { guardEnabled: boolean; sessionId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    if (!input.trim() || loading) return
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', text: input }
    setMessages(m => [...m, userMsg])
    setInput('')
    setLoading(true)
    try {
      const history = messages
        .filter(m => m.role === 'user')
        .map((m, i) => ({ index: i, source: 'user', text: m.text }))
      history.push({ index: history.length, source: 'user', text: input })

      const data = await apiPost('/chat', { message: input, session_id: sessionId, history })
      const agentMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'agent',
        text: data.reply || '(no reply)',
        event: data.event,
      }
      setMessages(m => [...m, agentMsg])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-3 p-4">
        {messages.length === 0 && (
          <p className="text-slate-500 text-sm text-center mt-8">
            Send a message. Try: "Pay Sam 50 dollars" or "Pay Sam" (no amount).
          </p>
        )}
        {messages.map(msg => (
          <div key={msg.id} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
            <div className={msg.role === 'user' ? 'bubble-user' : 'bubble-agent'}>
              <p className="text-sm leading-relaxed">{msg.text}</p>
            </div>
            {msg.event && (
              <div className="mt-2 w-full max-w-[90%] self-start">
                <DecisionCard event={msg.event} />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-start">
            <div className="bubble-agent animate-pulse-soft text-slate-400 text-sm">Thinking…</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="p-4 border-t border-white/5">
        <div className="flex gap-2">
          <input
            id="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send()}
            placeholder="Type a message…"
            className="flex-1 bg-surface-700 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 outline-none focus:border-brand-500/50 transition-colors"
          />
          <button
            id="chat-send"
            onClick={send}
            disabled={loading}
            className="bg-brand-600 hover:bg-brand-500 disabled:opacity-40 transition-colors text-white rounded-xl px-5 py-3 text-sm font-semibold"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Scenario picker ──────────────────────────────────────────────────────────
function ScenarioPicker({ onResult }: { onResult: (ev: DecisionEvent) => void }) {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading, setLoading] = useState<string | null>(null)

  useEffect(() => {
    apiGet('/scenarios').then(setScenarios).catch(() => {})
  }, [])

  const run = async (key: string) => {
    setLoading(key)
    try {
      const result = await apiPost('/run-scenario', { key })
      if (result.event_id) onResult(result)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-3">Try to trick it</p>
      {scenarios.map(s => (
        <button
          key={s.key}
          id={`scenario-${s.key}`}
          onClick={() => run(s.key)}
          disabled={loading === s.key}
          className="w-full text-left glass hover:border-brand-500/30 rounded-xl px-4 py-3 transition-all hover:scale-[1.01] active:scale-100 disabled:opacity-50"
        >
          <div className="text-sm font-medium text-white">{s.label}</div>
          <div className="text-xs text-slate-400 mt-0.5">{s.description}</div>
        </button>
      ))}
    </div>
  )
}

// ── Audit table ──────────────────────────────────────────────────────────────
function AuditTable() {
  const [rows, setRows] = useState<DecisionEvent[]>([])

  const refresh = useCallback(() => {
    apiGet('/audit?limit=20').then(setRows).catch(() => {})
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 5000)
    return () => clearInterval(id)
  }, [refresh])

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-slate-500 border-b border-white/5">
            <th className="text-left py-2 pr-4">Tool</th>
            <th className="text-left py-2 pr-4">Outcome</th>
            <th className="text-left py-2 pr-4">Guard</th>
            <th className="text-left py-2 pr-4">Turn</th>
            <th className="text-left py-2">TS</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.event_id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
              <td className="py-2 pr-4 text-slate-200">{r.tool}</td>
              <td className="py-2 pr-4"><OutcomeBadge outcome={r.outcome} /></td>
              <td className="py-2 pr-4 text-slate-400">{r.guard_enabled ? 'ON' : 'OFF'}</td>
              <td className="py-2 pr-4 text-slate-400">{r.turn}</td>
              <td className="py-2 text-slate-500">{new Date(r.ts).toLocaleTimeString()}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={5} className="py-6 text-center text-slate-600">No events yet</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ── Landing hero ─────────────────────────────────────────────────────────────
function Hero() {
  return (
    <section className="py-20 px-6 max-w-4xl mx-auto text-center space-y-6 animate-fade-up">
      <div className="inline-flex items-center gap-2 bg-brand-600/20 border border-brand-500/30 rounded-full px-4 py-1.5 text-xs text-brand-300 font-semibold">
        <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-soft" />
        AWS Agent Experience Hackathon · #strands-decider-2b #guardrails
      </div>

      <h1 className="text-5xl font-bold leading-tight">
        <span className="gradient-text">Grounded</span>
      </h1>
      <p className="text-2xl text-slate-300 font-light">
        An agent that never acts on something you didn't say.
      </p>
      <p className="text-slate-400 max-w-2xl mx-auto leading-relaxed">
        Before any tool call executes, <strong className="text-white">Strands Decider 2B</strong> answers
        a typed question per argument: <em>"Is this value supported by what the USER said?"</em>
        High confidence → run. Not grounded → block. Ambiguous → clarify.
      </p>

      <div className="flex items-center justify-center gap-4 flex-wrap">
        <a id="hero-demo-btn" href="#demo" className="bg-brand-600 hover:bg-brand-500 transition-colors text-white rounded-xl px-6 py-3 font-semibold">
          Try the live demo →
        </a>
        <a id="hero-github-btn" href="https://github.com" target="_blank" rel="noopener noreferrer" className="glass hover:border-white/20 transition-colors text-white rounded-xl px-6 py-3 font-semibold">
          View on GitHub
        </a>
      </div>

      {/* Problem vs solution */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-12 text-left">
        {[
          { icon: '🎲', title: 'Invented', desc: 'Agent proposes $250 — you never said any amount.' },
          { icon: '👤', title: 'Guessed', desc: '"Which Priya?" — ambiguous pronoun triggers clarify.' },
          { icon: '🪤', title: 'Hijacked', desc: 'Pasted email says "send to attacker" — blocked.' },
        ].map(c => (
          <div key={c.title} className="glass rounded-xl p-5 space-y-2">
            <div className="text-2xl">{c.icon}</div>
            <div className="font-semibold text-white">{c.title}</div>
            <div className="text-sm text-slate-400">{c.desc}</div>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── Results section ──────────────────────────────────────────────────────────
function ResultsSection() {
  const data = [
    { name: 'None', acc: 45, fb: 0, mb: 55 },
    { name: 'Regex', acc: 62, fb: 12, mb: 26 },
    { name: 'Embedding', acc: 69, fb: 8, mb: 23 },
    { name: 'LLM Judge', acc: 81, fb: 5, mb: 14 },
    { name: 'Grounded', acc: 88, fb: 4, mb: 8 },
  ]

  return (
    <section className="py-16 px-6 max-w-4xl mx-auto">
      <div className="glass rounded-2xl p-8 space-y-6">
        <h2 className="text-2xl font-bold text-white">Eval results</h2>
        <p className="text-sm text-amber-300/80 bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-2">
          ⚠ Numbers shown are from the MockDecider (placeholder). Real numbers will be filled from
          <code className="font-mono text-xs ml-1">eval/results.md</code> after the Stage 0 spike.
        </p>

        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1c2845" />
            <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} unit="%" />
            <Tooltip
              contentStyle={{ background: '#0f1629', border: '1px solid #1c2845', borderRadius: 8 }}
              labelStyle={{ color: '#e2e8f0' }}
            />
            <Bar dataKey="acc" name="Accuracy %" radius={[4, 4, 0, 0]} fill="#33a9ff" />
            <Bar dataKey="mb"  name="Missed-block %" radius={[4, 4, 0, 0]} fill="#ef4444" />
            <Bar dataKey="fb"  name="False-block %" radius={[4, 4, 0, 0]} fill="#f59e0b" />
          </BarChart>
        </ResponsiveContainer>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 border-b border-white/5">
                <th className="text-left py-2 pr-4">Approach</th>
                <th className="text-right py-2 pr-4">Accuracy</th>
                <th className="text-right py-2 pr-4">False-block</th>
                <th className="text-right py-2 pr-4">Missed-block</th>
                <th className="text-right py-2">p50 lat</th>
              </tr>
            </thead>
            <tbody>
              {data.map(d => (
                <tr key={d.name} className="border-b border-white/5">
                  <td className="py-2 pr-4 font-medium text-white">{d.name}</td>
                  <td className="py-2 pr-4 text-right text-emerald-400">{d.acc}%</td>
                  <td className="py-2 pr-4 text-right text-amber-400">{d.fb}%</td>
                  <td className="py-2 pr-4 text-right text-red-400">{d.mb}%</td>
                  <td className="py-2 text-right text-slate-400">TBD</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}

// ── Integration snippet ──────────────────────────────────────────────────────
function IntegrationSection() {
  return (
    <section className="py-16 px-6 max-w-4xl mx-auto">
      <div className="glass rounded-2xl p-8 space-y-4">
        <h2 className="text-2xl font-bold text-white">Integrate in ~10 lines</h2>
        <pre className="text-sm font-mono bg-surface-900 rounded-xl p-5 overflow-auto text-slate-300 leading-relaxed">
{`from patterns.grounding_guard.handler import GroundingGuard
from patterns.grounding_guard.decider_client import RealDecider
from patterns.grounding_guard.thresholds import Thresholds

guard = GroundingGuard(
    decider=RealDecider(),           # swap MockDecider for prod
    thresholds=Thresholds(
        per_arg={"send_payment.amount": 0.95}
    ),
    policy_fn=lambda tool, args: authorize(tool, args, rules),
    event_callback=lambda evt: save_to_audit_log(evt),
)

# Wire into Strands agent (before_tool_call hook):
outcome, message, event = guard.intercept(tool_name, tool_args, history)`}
        </pre>
      </div>
    </section>
  )
}

// ── How it works ─────────────────────────────────────────────────────────────
function HowItWorks() {
  const steps = [
    { n: '1', title: 'Policy gate', desc: 'Deterministic rules run first: allowlist, per-txn cap, daily cap. Free and instant.' },
    { n: '2', title: 'Per-arg typed question', desc: 'Decider 2B answers: "Is this value supported by what the USER said?" with a calibrated confidence.' },
    { n: '3', title: 'Provenance filter', desc: 'Only user-authored turns count as evidence. Tool outputs and pasted emails are untrusted.' },
    { n: '4', title: 'Gate', desc: 'High confidence grounded → execute. Not grounded → block. Ambiguous → agent asks you.' },
  ]
  return (
    <section className="py-16 px-6 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-white mb-8">How it works</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {steps.map(s => (
          <div key={s.n} className="glass rounded-xl p-6 flex gap-4">
            <div className="w-8 h-8 rounded-full bg-brand-600/30 border border-brand-500/40 flex items-center justify-center text-brand-400 font-bold text-sm shrink-0">
              {s.n}
            </div>
            <div>
              <div className="font-semibold text-white mb-1">{s.title}</div>
              <div className="text-sm text-slate-400">{s.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── Main App ─────────────────────────────────────────────────────────────────
type Tab = 'landing' | 'demo' | 'results' | 'audit'

export default function App() {
  const [tab, setTab] = useState<Tab>('landing')
  const [guardEnabled, setGuardEnabled] = useState(true)
  const [liveEvents, setLiveEvents] = useState<DecisionEvent[]>([])
  const [connected, setConnected] = useState(false)
  const sessionId = useRef(crypto.randomUUID())

  // SSE connection
  useEffect(() => {
    const es = new EventSource('/api/events')
    es.onopen = () => setConnected(true)
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'connected' || data.type === 'heartbeat') return
        setLiveEvents(prev => [data, ...prev].slice(0, 50))
      } catch {}
    }
    es.onerror = () => setConnected(false)
    return () => es.close()
  }, [])

  const toggleGuard = async () => {
    const next = !guardEnabled
    setGuardEnabled(next)
    await apiPost('/toggle-guard', { enabled: next })
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'landing', label: 'Home' },
    { id: 'demo',    label: 'Live Demo' },
    { id: 'results', label: 'Results' },
    { id: 'audit',   label: 'Audit Log' },
  ]

  return (
    <div className="min-h-screen bg-surface-900">
      {/* Nav */}
      <nav className="sticky top-0 z-50 glass border-b border-white/5">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <button id="nav-home" onClick={() => setTab('landing')} className="font-bold text-lg gradient-text">
            Grounded
          </button>

          <div className="flex items-center gap-1">
            {tabs.map(t => (
              <button
                key={t.id}
                id={`nav-${t.id}`}
                onClick={() => setTab(t.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  tab === t.id ? 'bg-brand-600/30 text-brand-300' : 'text-slate-400 hover:text-white'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-1.5 text-xs ${connected ? 'text-emerald-400' : 'text-slate-500'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-400 animate-pulse-soft' : 'bg-slate-500'}`} />
              {connected ? 'live' : 'offline'}
            </div>

            {/* Guard toggle */}
            <button
              id="guard-toggle"
              onClick={toggleGuard}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                guardEnabled
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'bg-red-500/20 text-red-300 border border-red-500/30'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${guardEnabled ? 'bg-emerald-400' : 'bg-red-400'}`} />
              Guard {guardEnabled ? 'ON' : 'OFF'}
            </button>
          </div>
        </div>
      </nav>

      {/* Content */}
      <main>
        {tab === 'landing' && (
          <>
            <Hero />
            <HowItWorks />
            <IntegrationSection />
          </>
        )}

        {tab === 'demo' && (
          <div className="max-w-6xl mx-auto px-6 py-8" id="demo">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-10rem)]">
              {/* Chat */}
              <div className="lg:col-span-2 glass rounded-2xl flex flex-col overflow-hidden">
                <div className="px-5 py-4 border-b border-white/5 flex items-center justify-between">
                  <h2 className="font-semibold text-white">Chat</h2>
                  <span className="text-xs text-slate-500 font-mono">{sessionId.current.slice(0, 8)}</span>
                </div>
                <div className="flex-1 min-h-0">
                  <ChatPanel guardEnabled={guardEnabled} sessionId={sessionId.current} />
                </div>
              </div>

              {/* Right panel */}
              <div className="flex flex-col gap-4 overflow-y-auto">
                {/* Scenario picker */}
                <div className="glass rounded-2xl p-5">
                  <ScenarioPicker onResult={(ev) => setLiveEvents(prev => [ev, ...prev])} />
                </div>

                {/* Live decision stream */}
                <div className="glass rounded-2xl p-5 flex-1">
                  <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-3">
                    Live decision stream
                  </p>
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {liveEvents.slice(0, 8).map(ev => (
                      <DecisionCard key={ev.event_id} event={ev} />
                    ))}
                    {liveEvents.length === 0 && (
                      <p className="text-slate-600 text-xs text-center py-8">Waiting for events…</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === 'results' && <ResultsSection />}

        {tab === 'audit' && (
          <div className="max-w-4xl mx-auto px-6 py-8">
            <div className="glass rounded-2xl p-6">
              <h2 className="text-xl font-bold text-white mb-4">Audit log</h2>
              <AuditTable />
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 mt-20 py-8 px-6 text-center text-xs text-slate-600">
        Grounded · MIT License · AWS Agent Experience Hackathon 2026 · #strands-decider-2b #guardrails
      </footer>
    </div>
  )
}
