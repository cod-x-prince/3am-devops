build-rust:
	maturin develop --release

install:
	pip install -e '.[dev]'

train:
	python training/train.py

eval:
	python training/eval.py

backtest:
	python -m training.backtest --agent-mode greedy --max-incidents 50 --output backtest_report.json

api:
	uvicorn api.main:app --reload --port 8000

dashboard:
	cd dashboard && npm run dev

demo:
	make api & make dashboard

test:
	pytest tests/

lint:
	ruff check . && black --check .
