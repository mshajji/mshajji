import wntr
from deap import base, creator, tools, algorithms
import numpy as np
import random
import logging

logger = logging.getLogger(__name__)

def evaluate_network(individual, wn, target_pipes, available_diameters, diameter_costs, min_pressure):
    # It's important to reset the simulation state or use a copy if the simulator mutates it irreparably.
    # WNTR simulator usually requires a fresh model to avoid issues with repeated runs,
    # but we can copy the model object in memory to avoid parsing the inp file repeatedly.
    import copy
    wn_eval = copy.deepcopy(wn)
    cost = 0

    # Set pipe diameters for targeted pipes
    for i, pipe_name in enumerate(target_pipes):
        pipe = wn_eval.get_link(pipe_name)
        diameter = available_diameters[individual[i]]
        # Convert to meters if EPANET expects it, or keep consistent with inp
        pipe.diameter = diameter
        cost += diameter_costs[diameter] * pipe.length

    # We may also want to add the cost of the existing pipes that aren't being optimized
    # if we want the total network cost, but usually optimization focuses on the variable cost.
    # For now, we'll just consider the cost of the targeted pipes for the optimization objective.

    sim = wntr.sim.EpanetSimulator(wn_eval)
    try:
        results = sim.run_sim()
        # Evaluate pressures at all time steps
        pressures = results.node['pressure']
        junction_names = wn_eval.junction_name_list

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

def optimize_pipes(inp_file, available_diameters, target_pipes=None, diameter_costs=None, min_pressure=20,
                   pop_size=50, ngen=50, cxpb=0.5, mutpb=0.2):
    """
    Optimizes pipe diameters in an EPANET network to minimize cost while satisfying a minimum pressure constraint.
    Uses a genetic algorithm (DEAP).

    :param inp_file: Path to the EPANET .inp file.
    :param available_diameters: List of available discrete pipe diameters.
    :param target_pipes: List of pipe names/IDs to optimize. If None, all pipes are optimized.
    :param diameter_costs: Dictionary mapping diameter to cost per unit length. If None, cost is assumed to be proportional to D^2.
    :param min_pressure: Minimum allowable pressure at all junctions.
    :param pop_size: Population size for the genetic algorithm.
    :param ngen: Number of generations.
    :param cxpb: Crossover probability.
    :param mutpb: Mutation probability.
    :return: A dictionary mapping targeted pipe names to their optimal diameter, and the best cost found.
    """
    wn = wntr.network.WaterNetworkModel(inp_file)
    if target_pipes is None:
        target_pipes = wn.pipe_name_list

    if diameter_costs is None:
        diameter_costs = {d: d**2 for d in available_diameters}

    if not hasattr(creator, "FitnessMin"):
        creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    if not hasattr(creator, "Individual"):
        creator.create("Individual", list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()
    # Gene is an index of the available_diameters list
    toolbox.register("attr_diameter_idx", random.randint, 0, len(available_diameters)-1)
    toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.attr_diameter_idx, n=len(target_pipes))
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    toolbox.register("evaluate", evaluate_network, wn=wn,
                     target_pipes=target_pipes,
                     available_diameters=available_diameters,
                     diameter_costs=diameter_costs,
                     min_pressure=min_pressure)

    # Use uniform crossover if length is < 2 (cxTwoPoint fails on length 1)
    if len(target_pipes) < 2:
        toolbox.register("mate", tools.cxUniform, indpb=0.5)
    else:
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
    best_diameters = {target_pipes[i]: available_diameters[best_ind[i]] for i in range(len(target_pipes))}
    best_cost = best_ind.fitness.values[0]

    return best_diameters, best_cost

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Optimize pipe diameters in an EPANET network.")
    parser.add_argument("inp_file", type=str, help="Path to the EPANET .inp file.")
    parser.add_argument("--available_diameters", type=float, nargs='+', required=True,
                        help="List of available discrete pipe diameters (space-separated).")
    parser.add_argument("--target_pipes", type=str, nargs='*', default=None,
                        help="List of pipe IDs to optimize (space-separated). If omitted, all pipes are optimized.")
    parser.add_argument("--min_pressure", type=float, default=20.0,
                        help="Minimum allowable pressure at all junctions.")
    parser.add_argument("--pop_size", type=int, default=50,
                        help="Population size for the genetic algorithm.")
    parser.add_argument("--ngen", type=int, default=50,
                        help="Number of generations for the genetic algorithm.")

    args = parser.parse_args()

    print(f"Optimizing network from {args.inp_file}...")

    try:
        best_diams, cost = optimize_pipes(
            inp_file=args.inp_file,
            available_diameters=args.available_diameters,
            target_pipes=args.target_pipes,
            min_pressure=args.min_pressure,
            pop_size=args.pop_size,
            ngen=args.ngen
        )
        print("\n--- Optimization Results ---")
        print(f"Best Cost: {cost}")
        print("Best Diameters:")
        for p, d in best_diams.items():
            print(f"  Pipe {p}: {d}")
    except Exception as e:
        print(f"Error during optimization: {e}")
        sys.exit(1)
