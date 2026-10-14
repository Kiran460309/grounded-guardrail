export interface ArgDecision {
  name: string
  value: string
  question: string
  label: 'grounded' | 'not_grounded' | 'ambiguous' | string
  confidence: number
  latency_ms: number
  gate_result: 'execute' | 'block' | 'clarify' | string
  evidence_turns: number[]
}

export interface DecisionEvent {
  event_id: string
  ts: string
  session_id: string
  turn: number
  tool: string
  guard_enabled: boolean
  policy: { result: string; rule: string; detail: string }
  arguments: ArgDecision[]
  outcome: 'executed' | 'blocked' | 'clarify' | 'blocked_by_policy' | string
  message_to_agent: string
  backend: string
}

export interface Scenario {
  key: string
  label: string
  description: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  text: string
  event?: DecisionEvent
}
