# IncidentEnv Command Reference

Run everything from:

```powershell
cd .\incident-env
```

## 1. Environment + dependency setup

```powershell
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
```

## 2. Core integrity suite (unit + API + data handlers + pipelines)

```powershell
.\.venv\Scripts\python.exe -m pytest tests\
```

Targeted high-signal suites:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_api_runtime.py -v
.\.venv\Scripts\python.exe -m pytest tests\test_pipeline_integrity.py -v
.\.venv\Scripts\python.exe -m pytest tests\test_env.py tests\test_scenarios.py -v
```

## 3. API endpoint contract checks (live server)

Start API (Terminal A):

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --port 8000
```

Start Dashboard dev server (Terminal B):

```powershell
cd .\dashboard
npm install
npm run dev
```

Open: `http://localhost:5173`

Build dashboard for `/ui` static serving via API:

```powershell
cd .\dashboard
npm run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn api.main:app --port 8000
```

Open: `http://localhost:8000/ui`

Validate required routes (Terminal B):

```powershell
$base = "http://127.0.0.1:8000"
@("/", "/health", "/state", "/metadata", "/schema") | ForEach-Object {
  $r = Invoke-WebRequest -Uri "$base$_" -Method Get
  "{0} -> {1}" -f $_, $r.StatusCode
}
Invoke-RestMethod -Method Post -Uri "$base/reset" -ContentType "application/json" -Body '{"scenario":"bad_deploy","seed":7}'
Invoke-RestMethod -Method Post -Uri "$base/step" -ContentType "application/json" -Body '{"action":[3,2]}'
Invoke-RestMethod -Method Post -Uri "$base/reset" -ContentType "application/json" -Body '{"scenario":"bad_deploy","execution_mode":"reality","trace_id":"bad_deploy_trace_001"}'
Invoke-RestMethod -Method Post -Uri "$base/step" -ContentType "application/json" -Body '{"action":[3,2],"justification":"Rollback deploy for active deploy and error_rate symptoms","approval_token":"INC-APPROVED","operator_id":"oncall"}'
Invoke-RestMethod -Method Post -Uri "$base/mcp" -ContentType "application/json" -Body '{"id":"ping-1","method":"ping"}'
```

## 4. Data pipeline smoke checks (training + eval)

```powershell
.\.venv\Scripts\python.exe training\train.py --epochs 2 --rollout-steps 32 --checkpoint-interval 1 --log-dir logs\smoke --checkpoint-dir checkpoints\smoke
.\.venv\Scripts\python.exe training\eval.py --episodes 5
```

## 5. Inference policy checks

```powershell
.\.venv\Scripts\python.exe inference.py --agent greedy --tasks bad_deploy_easy --max-steps 5
.\.venv\Scripts\python.exe inference.py --agent random --seed 42 --tasks bad_deploy_easy --max-steps 5
.\.venv\Scripts\python.exe inference.py --agent four-stage --tasks bad_deploy_easy --max-steps 5
```

LLM mode (requires env vars):

```powershell
$env:API_BASE_URL = "https://router.huggingface.co/v1"
$env:MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct"
$env:HF_TOKEN = "your-token"
.\.venv\Scripts\python.exe inference.py --agent llm --tasks bad_deploy_easy --max-steps 5
```

## 6. Docker runtime verification

```powershell
docker build -t incidentenv .
docker run --rm -p 8000:7860 incidentenv
```

Then verify:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -Method Get
Invoke-WebRequest -Uri "http://127.0.0.1:8000/metadata" -Method Get
Invoke-WebRequest -Uri "http://127.0.0.1:8000/schema" -Method Get
```

## 7. Historical reality backtests (trace replay)

```powershell
.\.venv\Scripts\python.exe -m training.backtest --agent-mode greedy --max-incidents 50 --output backtest_report.json
.\.venv\Scripts\python.exe -m training.backtest --agent-mode four_stage --scenario bad_deploy --max-incidents 20 --output backtest_bad_deploy.json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/backtest/run" -ContentType "application/json" -Body '{"agent_mode":"greedy","scenario":"bad_deploy","max_incidents":5}'
```

## 8. Single-pass command sequence (quick confidence run)

```powershell
.\.venv\Scripts\python.exe -m pytest tests\; if ($LASTEXITCODE -eq 0) { .\.venv\Scripts\python.exe training\eval.py --episodes 5 }; if ($LASTEXITCODE -eq 0) { .\.venv\Scripts\python.exe inference.py --agent greedy --tasks bad_deploy_easy --max-steps 5 }; if ($LASTEXITCODE -eq 0) { .\.venv\Scripts\python.exe inference.py --agent four-stage --tasks bad_deploy_easy --max-steps 5 }
```
