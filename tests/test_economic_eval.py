import pytest
import os
import wntr
from src.economic_eval import optimize_pipes

DUMMY_INP_PATH = "dummy.inp"

def setup_module(module):
    # Ensure the dummy inp file exists
    inp_content = """[TITLE]
Dummy Network

[JUNCTIONS]
;ID              Elev        Demand      Pattern
 1               0           0
 2               0           100
 3               0           100

[RESERVOIRS]
;ID              Head        Pattern
 4               100

[PIPES]
;ID              Node1           Node2           Length      Diameter    Roughness   MinorLoss   Status
 1               4               1               1000        300         100         0           Open
 2               1               2               1000        300         100         0           Open
 3               1               3               1000        300         100         0           Open

[PUMPS]
[VALVES]
[TAGS]
[DEMANDS]
[STATUS]
[PATTERNS]
[CURVES]
[CONTROLS]
[RULES]
[ENERGY]
[EMITTERS]
[QUALITY]
[SOURCES]
[REACTIONS]
[MIXING]

[TIMES]
 Duration            0:00
 Hydraulic Timestep  1:00
 Quality Timestep    0:05
 Pattern Timestep    1:00
 Pattern Start       0:00
 Report Timestep     1:00
 Report Start        0:00
 Start ClockTime     12 am
 Statistic           None

[REPORT]
 Status              No
 Summary             No
 Page                0

[OPTIONS]
 Units               LPS
 Headloss            H-W
 Specific Gravity    1.0
 Viscosity           1.0
 Trials              40
 Accuracy            0.001
 CHECKFREQ           2
 MAXCHECK            10
 DAMPLIMIT           0
 Unbalanced          Continue 10
 Pattern             1
 Demand Multiplier   1.0
 Emitter Exponent    0.5
 Quality             None mg/L
 Diffusivity         1.0
 Tolerance           0.01

[END]
"""
    with open(DUMMY_INP_PATH, "w") as f:
        f.write(inp_content)

def teardown_module(module):
    if os.path.exists(DUMMY_INP_PATH):
        os.remove(DUMMY_INP_PATH)

def test_optimize_pipes():
    available_diameters = [100, 200, 300, 400]
    best_diameters, best_cost = optimize_pipes(
        inp_file=DUMMY_INP_PATH,
        available_diameters=available_diameters,
        min_pressure=20,
        pop_size=10,
        ngen=5
    )

    # Check return types
    assert isinstance(best_diameters, dict)
    assert isinstance(best_cost, float)

    # Check that it returns diameters for all pipes
    wn = wntr.network.WaterNetworkModel(DUMMY_INP_PATH)
    for pipe_name in wn.pipe_name_list:
        assert pipe_name in best_diameters
        assert best_diameters[pipe_name] in available_diameters
