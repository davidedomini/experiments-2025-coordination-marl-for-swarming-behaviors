from curses.ascii import SI
import sys
import os
from vmas import make_env
import torch

scenarios_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'scenarios'))
training_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'training'))
simulation_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'simulation'))

sys.path.insert(0, scenarios_dir)
sys.path.insert(1, training_dir)
sys.path.insert(2, simulation_dir)

from train_gcn_dqn import GCN
from cohesion_scenario import CohesionScenario
from simulator import Simulator

if __name__ == "__main__":

    env = make_env(
        CohesionScenario(),
        scenario_name="test_gcn_vmas",
        num_envs=1,
        device="cpu",
        continuous_actions=False,
        dict_spaces=True,
        wrapper=None,
        seed=None,
        n_agents=9,
        max_steps= 100
    )

    models_dir = "models/"

    model = GCN(input_dim=5, hidden_dim=32, output_dim=9)
    model.load_state_dict(torch.load(models_dir + 'cohesion_collision.pth'))

    model.eval()
    print("Cohesion model loaded successfully!")

    simulator = Simulator(env, model)
    simulator.run_simulation()