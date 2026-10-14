# 03 — Tech stack
| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+, uv for env | typed, pytest |
| Agent | Strands Agents SDK | InterventionHandler hook — verify exact API in docs |
| LLM | Claude on Amazon Bedrock via boto3/Strands | confirm model ID + region in console (us-east-1/us-west-2 safest) |
| Decision model | Strands Decider 2B, local | requirements UNVERIFIED -> Stage 0 |
| Backend | FastAPI + uvicorn, SSE (sse-starlette) | real-time decision stream |
| Storage | SQLite (audit + eval runs) | zero setup |
| Eval | pytest + scripts, pandas, matplotlib | threshold curve + results table |
| Baselines | regex/fuzzy (rapidfuzz), embeddings (Bedrock Titan or local small model), LLM-judge (Bedrock) | measure real latency/cost |
| Frontend | Vite + React + TypeScript + Tailwind + Recharts | landing + dashboard + results in one app |
| Hosting | EC2 (backend+Decider), S3+CloudFront (frontend) | "working agent on AWS" |
| Tooling | GitHub, GitHub Actions (lint+tests), OBS for video, Mermaid for diagrams | |
| Vibe-coding IDE | Antigravity (agent reads AGENTS.md + /docs) | commit per stage |
