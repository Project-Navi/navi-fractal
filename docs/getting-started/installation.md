# Installation

## Quick install

```bash
pip install navi-fractal
```

Python 3.12+ required. Zero runtime dependencies.

## Development setup

```bash
git clone https://github.com/Project-Navi/navi-fractal.git
cd navi-fractal
uv sync --group dev
uv run pytest              # run tests
uv run ruff check          # lint
uv run mypy src/           # type check
```

## Verify installation

```python
from navi_fractal import make_grid_graph, estimate_sandbox_dimension

grid = make_grid_graph(10, 10)
result = estimate_sandbox_dimension(grid, seed=42)
assert result.dimension is not None
print("navi-fractal is working.")
```
