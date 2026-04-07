# Bootstrap script for Native Windows environments
Write-Host "Pulling Llama3... this might take a few minutes"
ollama pull llama3

Write-Host "Creating Virtual Environment..."
python -m venv .venv

Write-Host "Building Rust core using maturin..."
.\.venv\Scripts\python.exe -m pip install maturin
.\.venv\Scripts\maturin.exe develop -m engine/Cargo.toml --release

Write-Host "Installing Python dependencies..."
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'

Write-Host "Installing dashboard dependencies..."
Push-Location dashboard
npm install
Pop-Location

Write-Host "Bootstrap complete! You can now start the api and dashboard."
