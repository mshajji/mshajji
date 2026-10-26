# EPANET Economic Evaluation Module

This is a module for evaluating economic aspects of an EPANET model, specifically targeting pipe diameter optimization using metaheuristics to satisfy hydraulic constraints like minimum pressure at lowest cost.

## Dependencies

Install the requirements using:
```bash
pip install -r requirements.txt
```

## Usage

You can use the `optimize_pipes` function from `src.economic_eval`:

```python
from src.economic_eval import optimize_pipes

# Optimize all pipes in the network
best_diameters, best_cost = optimize_pipes(
    inp_file="network.inp",
    available_diameters=[100, 200, 300, 400],
    min_pressure=20
)
print(best_diameters)

# Target specific pipes for optimization
best_diameters, best_cost = optimize_pipes(
    inp_file="network.inp",
    available_diameters=[100, 200, 300, 400],
    target_pipes=["pipe1", "pipe2"],
    min_pressure=20
)
print(best_diameters)
```
