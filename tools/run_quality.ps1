$ErrorActionPreference = "Stop"

uv run ruff format --check .
if ($LASTEXITCODE -ne 0) { throw "Ruff formatting gate failed." }
uv run ruff check .
if ($LASTEXITCODE -ne 0) { throw "Ruff lint gate failed." }
uv run mypy src/timbrescribe
if ($LASTEXITCODE -ne 0) { throw "Mypy gate failed." }
uv run pytest -m "not model and not packaging"
if ($LASTEXITCODE -ne 0) { throw "Pytest gate failed." }
