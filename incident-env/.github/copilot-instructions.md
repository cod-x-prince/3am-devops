# Copilot Instructions
- This is a Meta hackathon project. Prefer Meta's own libraries: TorchRL over Stable Baselines, Llama 3 over GPT/Claude, PyTorch over JAX.
- Rust simulation engine is performance-critical. Python is API compliance/orchestration.
- Full type annotations for Python functions. Use Pydantic.
- Reward functions return float in [-1.0, 1.0].
- OpenEnv and gymnasium API compliance.
- No synchronous ollama calls in training loop.
- PyO3 bindings: #[pyclass], #[pymethods], #[pymodule].
- Dashboard aesthetic: dark terminal look.
