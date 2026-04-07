import os
import json
from pathlib import Path

def create_file(path_str, content):
    p = Path(path_str)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)

base = "c:/Users/ssang/Downloads/Meta_Hackathon/incident-env"
Path(base).mkdir(parents=True, exist_ok=True)

# 2. Configs
create_file(f"{base}/Cargo.toml", """[workspace]
members = ["engine"]
resolver = "2"

[profile.release]
opt-level = 3
lto = true
""")

create_file(f"{base}/pyproject.toml", """[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "incident-env"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "openenv", "torch", "torchrl", "tensordict", "gymnasium", "numpy",
    "fastapi", "uvicorn", "websockets", "ollama", "pydantic"
]

[project.optional-dependencies]
dev = ["pytest", "black", "ruff", "tensorboard"]
""")

create_file(f"{base}/Makefile", """build-rust:
\tmaturin develop --release

install:
\tpip install -e '.[dev]'

train:
\tpython training/train.py

eval:
\tpython training/eval.py

api:
\tuvicorn api.main:app --reload --port 8000

dashboard:
\tcd dashboard && npm run dev

demo:
\tmake api & make dashboard

test:
\tpytest tests/

lint:
\truff check . && black --check .
""")

create_file(f"{base}/bootstrap.ps1", """# Bootstrap script for Native Windows environments
Write-Host "Pulling Llama3... this might take a few minutes"
ollama pull llama3

Write-Host "Building Rust core using maturin..."
python -m maturin develop --release

Write-Host "Installing Python dependencies..."
python -m pip install -e '.[dev]'

Write-Host "Installing dashboard dependencies..."
Push-Location dashboard
npm install
Pop-Location

Write-Host "Bootstrap complete! You can now start the api and dashboard."
""")

create_file(f"{base}/README.md", """# IncidentEnv
OpenEnv-compatible RL environment for autonomous production incident remediation.
Created for Meta PyTorch OpenEnv Hackathon x SST 2026.
""")

create_file(f"{base}/.github/copilot-instructions.md", """# Copilot Instructions
- This is a Meta hackathon project. Prefer Meta's own libraries: TorchRL over Stable Baselines, Llama 3 over GPT/Claude, PyTorch over JAX.
- Rust simulation engine is performance-critical. Python is API compliance/orchestration.
- Full type annotations for Python functions. Use Pydantic.
- Reward functions return float in [-1.0, 1.0].
- OpenEnv and gymnasium API compliance.
- No synchronous ollama calls in training loop.
- PyO3 bindings: #[pyclass], #[pymethods], #[pymodule].
- Dashboard aesthetic: dark terminal look.
""")

# 3. Rust Engine
create_file(f"{base}/engine/Cargo.toml", """[package]
name = "incident_core"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib", "rlib"]

[dependencies]
pyo3 = { version = "0.21", features = ["extension-module"] }
petgraph = "0.6"
rand = "0.8"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
numpy = "0.21"
""")

# Will implement Rust files individually via normal tasks later. Let's just create empty stubs for now to have structure
for rs in ["lib.rs", "service_graph.rs", "fault_injector.rs", "metrics_engine.rs"]:
    create_file(f"{base}/engine/src/{rs}", f"// stub for {rs}\n")

# 4. Python
for py in [
    "envs/__init__.py", "envs/incident_env.py", "envs/scenarios.py",
    "rewards/__init__.py", "rewards/mttr.py", "rewards/blast_radius.py", "rewards/false_alarm.py", "rewards/composite.py",
    "graders/__init__.py", "graders/programmatic.py", "graders/llm_grader.py",
    "training/__init__.py", "training/train.py", "training/curriculum.py", "training/eval.py",
    "tests/test_env.py", "tests/test_graders.py", "tests/test_smoke.py", "tests/test_scenarios.py",
    "api/__init__.py", "api/main.py"
]:
    create_file(f"{base}/{py}", f"# stub for {py}\n")

# JSON scenarios
scenarios = {
    "bad_deploy.json": {"name": "bad_deploy", "description": "New deploy causes err rate spike", "curriculum_level": 1, "topology": "star", "num_services": 12, "fault_sequence": [{"tick": 0, "fault_type": "BadDeploy", "target": 1}], "max_steps": 20, "success_condition": "all_healthy"},
    "cascade_timeout.json": {"name": "cascade_timeout", "description": "Upstream latency config", "curriculum_level": 2, "topology": "mesh", "num_services": 12, "fault_sequence": [{"tick": 0, "fault_type": "CascadeTimeout", "target": 0}], "max_steps": 20, "success_condition": "all_healthy"},
    "thundering_herd.json": {"name": "thundering_herd", "description": "Mass retry storm", "curriculum_level": 2, "topology": "star", "num_services": 12, "fault_sequence": [{"tick": 5, "fault_type": "ThunderingHerd", "target": 1}], "max_steps": 20, "success_condition": "all_healthy"},
    "split_brain.json": {"name": "split_brain", "description": "DB lag", "curriculum_level": 3, "topology": "random", "num_services": 12, "fault_sequence": [{"tick": 0, "fault_type": "SplitBrain", "target": 0}], "max_steps": 20, "success_condition": "all_healthy"},
    "multi_fault.json": {"name": "multi_fault", "description": "Simultaneous faults", "curriculum_level": 3, "topology": "random", "num_services": 12, "fault_sequence": [{"tick": 0, "fault_type": "MemoryLeak", "target": 2}, {"tick": 0, "fault_type": "BadDeploy", "target": 7}], "max_steps": 25, "success_condition": "all_healthy"}
}

for name, json_data in scenarios.items():
    create_file(f"{base}/scenarios/configs/{name}", json.dumps(json_data, indent=2))

# 6. React + D3 Dashboard
create_file(f"{base}/dashboard/package.json", """{
  "name": "incident-env-dashboard",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "eslint . --ext js,jsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "d3": "^7.8.5",
    "recharts": "^2.11.0",
    "framer-motion": "^11.0.3",
    "lucide-react": "^0.320.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.35",
    "tailwindcss": "^3.4.1",
    "vite": "^5.0.8"
  }
}
""")

create_file(f"{base}/dashboard/vite.config.js", """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
""")

create_file(f"{base}/dashboard/tailwind.config.js", """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'terminal-bg': '#080810',
        'terminal-green': '#00ff88',
        'terminal-yellow': '#ffcc00',
        'terminal-orange': '#ff8800',
        'terminal-red': '#ff3333',
        'terminal-cyan': '#00ccff'
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'monospace'],
      }
    },
  },
  plugins: [],
}
""")

create_file(f"{base}/dashboard/postcss.config.js", """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
""")

create_file(f"{base}/dashboard/index.html", """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>IncidentEnv Dashboard</title>
  </head>
  <body class="bg-terminal-bg text-white antialiased font-mono">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
""")

create_file(f"{base}/dashboard/src/index.css", """@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  display: flex;
  min-width: 320px;
  min-height: 100vh;
}
""")

for js in [
    "src/main.jsx", "src/App.jsx",
    "src/components/ServiceGraph.jsx", "src/components/MetricsFeed.jsx", "src/components/AgentLog.jsx", "src/components/ScoreCard.jsx",
    "src/hooks/useEpisodeStream.js"
]:
    create_file(f"{base}/dashboard/{js}", f"// stub for {js}\n")
