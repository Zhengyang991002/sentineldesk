# SentinelDesk

Multilingual (EN/DE) incident triage, escalation gate and precedent-grounded reply copilot.

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.prepare_data      # download CSV + official 80/20 split (seed 42)
python -m src.pipeline              # end-to-end smoke test
```
Set `ANTHROPIC_API_KEY` in your environment for LLM drafting (falls back to a template reply without it).

## Team ownership
| Owner | Files |
|---|---|
| Integrator | src/data.py, src/gate.py, src/pipeline.py, README |
| Teammate 1 | src/triage.py, scripts/evaluate.py |
| Teammate 2 | src/retrieval.py |
| Teammate 3 | src/generate.py, src/pii.py, src/lang.py |
| Teammate 4 | app.py, src/burst.py |

Interface contracts are in each module's docstring. Do not change return shapes.

## Leakage rules
Models and index are built on the KB `fit` part only; thresholds are tuned on `val`.
The test split's `answer` column is never written to disk.
