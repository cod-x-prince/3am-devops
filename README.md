# IncidentEnv - Meta Hackathon Submission

This repository contains **IncidentEnv**, an OpenEnv-compatible environment for autonomous incident remediation in microservice systems.

## Where to start

- Core project: `incident-env/`
- Submission config: `incident-env/openenv.yaml`
- Baseline runner: `incident-env/inference.py`
- API runtime: `incident-env/api/main.py`
- Team status trackers: `trackA.md`, `trackB.md`

## Quick run (Windows)

```powershell
cd incident-env
.\.venv\Scripts\python.exe -m pytest tests\
.\.venv\Scripts\python.exe inference.py
```

## Docker smoke run

```powershell
cd incident-env
docker build -t incidentenv-openenv .
docker run --rm -p 8000:8000 incidentenv-openenv
```

Expected key endpoints:

- `GET /`
- `GET /health`
- `POST /reset`
- `POST /step`
- `GET /state`
- `GET /metadata`
- `GET /schema`
- `POST /mcp`

## Submission ops checklist

- Set Hugging Face Space env vars: `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`
- Deploy the current `main` branch
- Run pre-validation against the live Space URL
- Keep inference stdout in strict `[START] / [STEP] / [END]` format

For full technical details and contract documentation, see:

- `API_CONTRACT.md`
- `ARCHITECTURE.md`
- `DEMO_GUIDE.md`
- `incident-env/README.md`
