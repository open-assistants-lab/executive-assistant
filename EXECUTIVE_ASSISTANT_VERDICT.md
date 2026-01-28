# Executive Assistant vs Clawdbot — Verdict

Date: 2026-01-26

## Executive Assistant (this codebase) — how it works
- Python, LangGraph-based ReAct agent with explicit graph nodes for model/tool calls.
- Multi-channel runtime with Telegram and HTTP (FastAPI) entrypoints.
- Tool-rich assistant: file ops, DB tools, vector store, web search, Python execution, OCR, reminders, and flow tooling.
- Storage-first design: thread/group/shared scoping across files, DB, and vector store; PostgreSQL checkpointing for conversation state.
- Background scheduler for reminders and scheduled flows.

## Clawdbot — how it works
- Gateway-centric architecture: a gateway process brokers all user requests and routes them to agents or device nodes.
- Dedicated gateway protocol over WebSocket with typed events (connect, message, AI flow, device status), and session metadata.
- Multi-surface messaging by design (e.g., Telegram, Discord, web) plus device nodes (e.g., Raspberry Pi, local services) connected through the gateway.
- Emphasis on security and pairing: per-agent secrets, role-based access, encrypted traffic, and a pairing flow for new endpoints.

## Key Differentiators
- **Control plane vs embedded runtime**: Clawdbot is built around a networked gateway/control plane with a protocol and device nodes; Executive Assistant is a self-contained agent runtime that directly hosts channels and tools.
- **Surface breadth**: Clawdbot is oriented toward broad multi-platform reach and device integration; Executive Assistant is optimized for Telegram/HTTP and deep tool usage in a single runtime.
- **Storage model**: Executive Assistant has a strict, built-in storage hierarchy (thread/group/shared) with DB/VS/file tooling; Clawdbot focuses more on routing, gateways, and distributed nodes than on embedded personal knowledge storage.
- **Primary use case**: Executive Assistant targets personal/group productivity workflows (timesheets, reminders, knowledge base). Clawdbot targets a cross-surface assistant and device-control ecosystem.

## Verdict
If you want a **tool-heavy, storage-centric assistant** that runs as a single service with strong data isolation and built-in workflows (reminders, knowledge base, ad‑hoc analysis), Executive Assistant is the better fit. If you want a **gateway-driven, multi-endpoint assistant** that can span many messaging surfaces and device nodes with a formal protocol and pairing/security model, Clawdbot is the better fit.

In short: Executive Assistant = deep local capability and structured memory; Clawdbot = broad reach and networked control plane.
