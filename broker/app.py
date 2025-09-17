import os, time, math, requests
from flask import Flask, request, jsonify
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# ---- Metrics
REQS = Counter("council_requests_total", "Total requests", ["spartan", "route"])
ERRS = Counter("council_errors_total", "Total errors", ["spartan", "route"])
TOK_IN  = Counter("council_tokens_in_total", "Prompt tokens", ["spartan"])
TOK_OUT = Counter("council_tokens_out_total", "Completion tokens", ["spartan"])
LAT  = Histogram("council_latency_ms", "Latency (ms)", buckets=(50,100,200,500,1000,2000,5000))

# ---- Config
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
TAG_MODEL = {
    "Tia":  "llama3.1:8b",        # Hestia — steady synthesizer
    "Olly": "qwen2.5-coder:7b",   # Apollo — code-focused
    "Mira": "mistral:7b"          # Artemis — fast scout
}

def approx_tokens(text: str) -> int:
    if not text: return 0
    return max(1, math.ceil(len(text) / 4))

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.get("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

@app.post("/query")
def query():
    start = time.time()
    data = request.get_json(silent=True)
    try:
        if not isinstance(data, dict):
            raise ValueError("invalid_json")

        spartan = data.get("tag", "Tia")
        route = spartan
        force_error = data.get("force_error", False)
        prompt = (data.get("query") or "Say hello from the Council.").strip()
        model = TAG_MODEL.get(spartan, TAG_MODEL["Tia"])

        if force_error:
            raise RuntimeError("forced")

        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=45
        )
        r.raise_for_status()
        payload = r.json()
        completion = payload.get("response", "") or ""
        in_tokens  = payload.get("prompt_eval_count", approx_tokens(prompt))
        out_tokens = payload.get("eval_count", approx_tokens(completion))

        REQS.labels(spartan=spartan, route=route).inc()
        TOK_IN.labels(spartan=spartan).inc(int(in_tokens))
        TOK_OUT.labels(spartan=spartan).inc(int(out_tokens))

        return jsonify(ok=True, spartan=spartan, route=route, model=model,
                       tokens_in=int(in_tokens), tokens_out=int(out_tokens),
                       response=completion[:240])
    except Exception:
        s = "Tia" if not isinstance(data, dict) else data.get("tag", "Tia")
        ERRS.labels(spartan=s, route=s).inc()
        return jsonify(ok=False, error="agent_error"), 500
    finally:
        LAT.observe((time.time() - start) * 1000.0)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
