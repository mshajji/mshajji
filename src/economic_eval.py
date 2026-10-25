import wntr
from deap import base, creator, tools, algorithms
import numpy as np
import random
import logging

logger = logging.getLogger(__name__)

def evaluate_network(individual, inp_file, available_diameters, diameter_costs, min_pressure):
    wn = wntr.network.WaterNetworkModel(inp_file)
    pipe_names = wn.pipe_name_list
    cost = 0

    # Set pipe diameters
    for i, pipe_name in enumerate(pipe_names):
        pipe = wn.get_link(pipe_name)
        diameter = available_diameters[individual[i]]
        # Convert to meters if EPANET expects it, or keep consistent with inp
        pipe.diameter = diameter
        cost += diameter_costs[diameter] * pipe.length

    sim = wntr.sim.EpanetSimulator(wn)
    try:
        results = sim.run_sim()
        # Evaluate pressures at all time steps
        pressures = results.node['pressure']
        junction_names = wn.junction_name_list

        if pressures.empty:
             return 1e9,

        # Minimum pressure across all junctions and all time steps
        min_node_pressure = pressures[junction_names].min().min()

        # Penalize if pressure constraint is violated
        if min_node_pressure < min_pressure:
            penalty = 1e6 * (min_pressure - min_node_pressure)
            cost += penalty
    except Exception as e:
        # Simulation failed
        logger.error(f"Simulation failed: {e}")
        cost = 1e9

    return cost,

def optimize_pipes(inp_file, available_diameters, diameter_costs=None, min_pressure=20,
                   pop_size=50, ngen=50, cxpb=0.5, mutpb=0.2):
    """
    Optimizes pipe diameters in an EPANET network to minimize cost while satisfying a minimum pressure constraint.
    Uses a genetic algorithm (DEAP).

    :param inp_file: Path to the EPANET .inp file.
    :param available_diameters: List of available discrete pipe diameters.
    :param diameter_costs: Dictionary mapping diameter to cost per unit length. If None, cost is assumed to be proportional to D^2.
    :param min_pressure: Minimum allowable pressure at all junctions.
    :param pop_size: Population size for the genetic algorithm.
    :param ngen: Number of generations.
    :param cxpb: Crossover probability.
    :param mutpb: Mutation probability.
    :return: A dictionary mapping pipe names to their optimal diameter, and the best cost found.
    """
    wn = wntr.network.WaterNetworkModel(inp_file)
    pipe_names = wn.pipe_name_list

    if diameter_costs is None:
        diameter_costs = {d: d**2 for d in available_diameters}

    if not hasattr(creator, "FitnessMin"):
        creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    if not hasattr(creator, "Individual"):
        creator.create("Individual", list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()
    # Gene is an index of the available_diameters list
    toolbox.register("attr_diameter_idx", random.randint, 0, len(available_diameters)-1)
    toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.attr_diameter_idx, n=len(pipe_names))
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    toolbox.register("evaluate", evaluate_network, inp_file=inp_file,
                     available_diameters=available_diameters,
                     diameter_costs=diameter_costs,
                     min_pressure=min_pressure)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", tools.mutUniformInt, low=0, up=len(available_diameters)-1, indpb=0.1)
    toolbox.register("select", tools.selTournament, tournsize=3)

    pop = toolbox.population(n=pop_size)
    hof = tools.HallOfFame(1)
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("min", np.min)
    stats.register("avg", np.mean)

    pop, log = algorithms.eaSimple(pop, toolbox, cxpb=cxpb, mutpb=mutpb, ngen=ngen,
                                   stats=stats, halloffame=hof, verbose=True)

    best_ind = hof[0]
    best_diameters = {pipe_names[i]: available_diameters[best_ind[i]] for i in range(len(pipe_names))}
    best_cost = best_ind.fitness.values[0]

    return best_diameters, best_cost
