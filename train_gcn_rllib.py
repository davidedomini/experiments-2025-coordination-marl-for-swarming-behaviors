import torch
import torch.nn.functional as F
from gym.spaces import Discrete
from torch_geometric.nn import GCNConv, global_mean_pool
from torch_geometric.data import Data, Batch
from ray.rllib.models.torch.torch_modelv2 import TorchModelV2
from ray.rllib.models import ModelCatalog
from ray.rllib.agents.ppo import PPOTrainer
from ray import tune
import ray
from vmas import make_env, Wrapper
from custom_scenario import CustomScenario
from ray.rllib.env import MultiAgentEnv
from ray.tune import register_env
from typing import Dict
import numpy as np

class GNNModel(torch.nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim):
        super(GNNModel, self).__init__()
        self.conv1 = GCNConv(input_dim, hidden_dim)
        self.conv2 = GCNConv(hidden_dim, output_dim)

    def forward(self, data):
        x, edge_index = data.x, data.edge_index
        x = F.relu(self.conv1(x, edge_index))
        x = self.conv2(x, edge_index)
        return F.log_softmax(x, dim=1)

def build_graph(observations):
    # Assume observations is a dict with agent ids as keys
    batch_size = list(observations.values())[0].size(0)
    num_agents = len(observations)
    
    # Concatenate observations along the batch dimension
    node_features = torch.cat([obs.view(batch_size, -1) for obs in observations.values()], dim=0)
    
    # Create edge indices for a fully connected graph among agents
    edge_index = []
    for i in range(num_agents):
        for j in range(num_agents):
            edge_index.append([i, j])
    edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
    
    # Create Data objects for each batch instance
    data_list = []
    for i in range(batch_size):
        data = Data(x=node_features[i * num_agents:(i + 1) * num_agents], edge_index=edge_index)
        data_list.append(data)
    
    # Use Batch from torch_geometric to handle a batch of graphs
    graph_data = Batch.from_data_list(data_list)
    return graph_data


class CustomGNNModel(TorchModelV2, torch.nn.Module):
    def __init__(self, obs_space, action_space, num_outputs, model_config, name):
        
        TorchModelV2.__init__(self, obs_space, action_space, num_outputs, model_config, name)
        torch.nn.Module.__init__(self)

        input_dim = 6 # Number of features per agent (6)
        hidden_dim = model_config.get("custom_model_config", {}).get("hidden_dim", 32)
        output_dim = 9  # Should match the number of actions (9)

        self.gnn = GNNModel(input_dim, hidden_dim, output_dim)

    def forward(self, input_dict, state, seq_lens):
        agent_states = input_dict["obs"]
        print("AGENT STATES SHAPE: ", {k: v.shape for k, v in agent_states.items()})

        graph_data = build_graph(agent_states)
        logits = self.gnn(graph_data)
        print("LOGITS SHAPE: ", logits.shape)  # Log the shape of logits

        return logits, state

    def value_function(self):
        return torch.zeros(1)


ModelCatalog.register_custom_model("custom_gnn_model", CustomGNNModel)

config = {
    "env": "custom_vmas_env",
    "env_config": {
        "num_agents": 2,
    },
    "model": {
        "custom_model": "custom_gnn_model",
        "custom_model_config": {
            "hidden_dim": 32,
        },
    },
    "framework": "torch",
    "num_workers": 1,
}

def env_creator(config: Dict):
    env = make_env(
        scenario=CustomScenario(),
        num_envs=1,
        device="cpu",
        continuous_actions=False,
        wrapper=Wrapper.RLLIB,
        max_steps=200,
        dict_spaces=True,
        n_agents=2,
    )
    obs = env.env.reset()
    return env

if not ray.is_initialized():
    ray.init()

register_env("custom_vmas_env", lambda config: env_creator(config))

trainer = PPOTrainer(config=config) 
for _ in range(100):
    result = trainer.train()
    print(result)
