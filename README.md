# AI Council — Local, Observable, Extensible

A **local-first multi-agent (“council”)** you can run on your own machine. It routes tagged prompts to specialized agents (models), executes tool calls via a safe protocol, and ships **observability out of the box** (logs, metrics, traces) so you can see exactly what’s happening. An optional macOS **menu-bar app** gives you a quick UI to send prompts and view responses.

> This README is **generic**: bring your own agent names, domain focus, and tone. Everything here is designed to be customized.

---

## Why this exists

- **Local-first privacy.** Keep prompts, data, and model weights on your machine.
- **Real observability.** Logs, metrics, and traces for every request and tool call.
- **Composable capabilities.** Add/allowlist tools behind a standard interface.
- **Easy to demo.** A toggleable demo mode and an optional menu-bar UI.

---

## High-level architecture

┌──────────┐      ┌────────────┐     ┌────────────────────────┐
│  Client  │  →   │   Broker   │  →  │   Model runner (LLM)   │
│ (CLI/UI) │      │ (router &  │     │  (e.g., Ollama)        │
│          │  ←   │  executor) │  ←  │                        │
└──────────┘      └────────────┘     └────────────────────────┘
│                    │                      │
│                    ├── MCP tools (FS/Git/HTTP/Shell…)*
│                    │
│                    └── Observability: Logs (Loki), Metrics (Prometheus),
│                        Traces (Tempo), Dashboards (Grafana)

\* *MCP = Model Context Protocol (or a similar “tool server” abstraction). The broker calls these tools with strict allowlists and JSON schemas.*

---

## Stack (defaults you can swap)

- **Models:** Llama 3.1 8B, Qwen2.5 7B / Coder 7B, Mistral 7B (via **Ollama**)  
- **Broker:** Router + simple planner/executor with tag→model mapping  
- **Observability (“one ring”):** Grafana (UI) + Loki (logs) + Prometheus (metrics) + Tempo (traces)  
- **Agent metrics exposed (Prometheus):**
  - `council_requests_total{spartan,route}`
  - `council_errors_total{spartan,route}`
  - `council_latency_ms_bucket` (Histogram in ms)
  - `council_tokens_in_total{spartan}`
  - `council_tokens_out_total{spartan}`

---

## Requirements

- **Docker** + **Docker Compose**
  - macOS on Apple Silicon: recommended **Colima** (`brew install colima docker docker-compose`)
  - Start with `colima start --memory 12 --cpu 4` (tune as needed)
- (Optional) **Node 18+** if you want the desktop menu-bar client

---

## Repository layout (core)
council/
├─ docker-compose.yml
├─ .env.example
├─ bootstrap.sh
├─ council.config.yaml                # agents, routing rules, guardrails
├─ data/                              # runtime data & artifacts
├─ mcp/                               # (optional) tool servers (filesystem/git/http/shell)
└─ observability/
├─ grafana/provisioning/{datasources,dashboards}/
├─ loki/config.yml
├─ tempo/config.yml
├─ prometheus/prometheus.yml
└─ alloy/config.alloy              # unified logs/metrics/traces shipper

---

---

## Quickstart (local)

1) **Clone & configure**
~~~bash
git clone <your-fork-url> council && cd council
cp .env.example .env
~~~

2) **Start the stack**
~~~bash
./bootstrap.sh
# or (manual):
# docker compose up -d ollama grafana prometheus loki tempo alloy
~~~

3) **Pull models (Ollama)**
~~~bash
curl -s http://localhost:11434/api/pull -d '{"name":"llama3.1:8b"}'
curl -s http://localhost:11434/api/pull -d '{"name":"qwen2.5:7b"}'
# add others you need (e.g., qwen2.5-coder:7b, mistral:7b)
~~~

4) **Open Grafana**
- Visit: `http://localhost:3000`
- Login with `.env` credentials (change them).
- Dashboard: **Council Home** (pre-provisioned)

5) **Ping the broker**
~~~bash
curl -s http://localhost:8080/health
curl -s -X POST http://localhost:8080/query \
  -H 'Content-Type: application/json' \
  -d '{"tag":"AgentA","query":"Say hi in one short sentence.","demo":true}'
~~~

> Calling from another computer? If containers bind to loopback, create a tunnel:
> ~~~bash
> ssh -fN -L 8081:localhost:8080 <host>
> # then hit:
> curl -s http://localhost:8081/health
> ~~~

---

## Configuration

### `.env` (excerpt)
~~~ini
LOG_LEVEL=info
COUNCIL_MODE=private           # private | demo
COUNCIL_DATA_DIR=./data

BROKER_PORT=8080
OLLAMA_URL=http://ollama:11434

GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin
~~~

### `council.config.yaml` (routing & guardrails)
~~~yaml
version: 1
demo_mode: ${COUNCIL_MODE}

spartans:   # rename to "agents" if you prefer
  - name: "AgentA"
    tag: "AgentA"
    model: "llama3.1:8b"
    capabilities:
      allow_mcp: ["filesystem","git","http"]
      deny_mcp: ["shell"]
  - name: "AgentB"
    tag: "AgentB"
    model: "qwen2.5-coder:7b"
    capabilities:
      allow_mcp: ["filesystem","git","shell"]
      deny_mcp: []

routing:
  default: "AgentA"
  rules:
    - when: "query.tag == 'AgentB'"
      route: "AgentB"

guardrails:
  tool_schema_enforced: true
  max_steps: 12
  step_timeout_s: 30
  redact_patterns:
    - "(?i)[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}"
    - "sk-[A-Za-z0-9]{20,}"
    - "Bearer\\s+[A-Za-z0-9._-]+"

artifacts:
  path: "${COUNCIL_DATA_DIR}/artifacts"
  keep_json_plans: true

demo:
  sandbox_paths:
    - "${COUNCIL_DATA_DIR}/demo"
  rate_limit_per_min: 10
  mcp_allowlist_only: true
~~~

### Tag → model mapping
- Tags (e.g., `AgentA`, `AgentB`) map to models (e.g., `llama3.1:8b`, `qwen2.5-coder:7b`) in the broker.
- Swap models freely. Prefer **Apache-2.0** model licenses when possible.
- On Apple Silicon, allocate enough RAM to Colima and use quantized weights for multiple concurrent models.

---

## Observability (the “one ring”)

- **Grafana** is pre-provisioned with:
  - Requests/Errors (5m), p95 Latency, Tokens In/Out
  - “By agent” variants
- **Prometheus** scrapes the broker’s `/metrics`
- **Loki** ingests JSON logs (one object per line)
- **Tempo** receives OpenTelemetry traces (optional; add from your broker)

**Common panel gotchas**
- Errors show *No data* → you haven’t triggered any in the range.
- Tokens show 0 → ensure your broker increments `council_tokens_*` and you’ve sent recent traffic.
- Multi-process metrics → prefer a single broker process for Prometheus or use a shared registry.

---

## Optional: macOS Menu-Bar UI (Electron)

- Minimal menubar to send prompts and preview responses.
- Uses a **preload IPC bridge** (no browser CORS/CSP issues).
- Points at your broker (locally or via `ssh -L 8081:localhost:8080 <host>`).

**Dev**
~~~bash
# in the UI project:
npm install
npm start
# in app DevTools:
localStorage.setItem('COUNCIL_BROKER','http://localhost:8081')
~~~

Replace this with Raycast / SwiftBar / SwiftUI / a CLI if you prefer.

---

## Security notes

- **Demo mode:** sandboxes writes, rate-limits requests, narrows tool allow-lists.
- **Public exposure:** reverse proxy (Caddy/Traefik), SSO (e.g., Authelia), or VPN (Tailscale).
- **Secrets:** keep `.env` out of git; use your OS keychain or a secret manager.
- **Logging:** redact emails, tokens, and sensitive IDs; hash where sensible.

---

## Customize your council

- **Agents:** rename, adjust domains, tune system prompts.
- **Tools:** per-agent allow/deny lists; add tool servers (fs/git/http/shell/…).
- **Routing:** rules by tag, keyword, or classifier.
- **Models:** choose models that fit your taste/hardware/license.
- **UI:** swap Electron for a native client or integrate into your editor.

---

## Troubleshooting

- **Docker daemon not found:** install Docker/Colima; `colima start --memory 12 --cpu 4`.
- **Cannot connect to Docker daemon:** `docker context use colima`.
- **Grafana “No data”:** confirm Prometheus target `broker:8080/metrics` is **UP**.
- **CORS/CSP in browsers:** enable CORS on the broker or use the Electron UI (IPC avoids CORS).
- **Host/LAN access:** many containers bind to loopback only; use an SSH tunnel or reverse proxy.

---

## Roadmap

- Multi-step planning with budgets and self-checks  
- Per-agent RBAC, quotas, and escalation rules  
- Expanded tool adapters (sheets, email, data warehouses)  
- Packaged installer for the menu-bar app  
- “Deploy in 10 minutes” starter kit

---

## License

Recommended: **Apache-2.0** for the council code, and Apache-friendly models/tools.

---

## Credits

Thanks to the open-source ecosystem: Grafana, Prometheus, Loki, Tempo, Ollama, and the growing family of open models. Customize freely and make it yours.
