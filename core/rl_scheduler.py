"""
Reinforcement Learning Scheduler for SCADA Load Shedding
Issue 1 FIX: This file was completely missing from the submitted codebase.
             Implements thesis Chapter 4.4.2 exactly.

Architecture
------------
* Custom OpenAI Gymnasium environment  (LoadSheddingEnv)
* Observation space: continuous vector encoding demand, weights,
  available supply, cyclic time-of-day
* Action space: Discrete — one allocation decision per feeder per step
  (full / partial / off)  mapped to {0%, 50%, 100%} of demand per feeder
* Reward: large negative for hospital outages, moderate negative for
  industrial, positive proportional to Jain's Fairness Index,
  small negative for over-generation
* Training: Proximal Policy Optimisation (PPO) via stable-baselines3
* Policy serialised to disk as  models/rl_policy.zip

Dependencies
------------
    pip install stable-baselines3 gymnasium
"""

from __future__ import annotations

import logging
import os
import math
import numpy as np
from typing import List, Dict, Optional, Tuple
from config import MODELS_DIR, RL_POLICY_PATH, RL_TOTAL_TIMESTEPS

logger = logging.getLogger(__name__)

os.makedirs(MODELS_DIR, exist_ok=True)
# Strip the .zip suffix — stable-baselines3 appends it automatically
RL_MODEL_PATH = RL_POLICY_PATH.replace(".zip", "")

# ------------------------------------------------------------------ #
# Tier weights and minimum-service ratios (matches LP / thesis)       #
# ------------------------------------------------------------------ #
TIER_W: Dict[str, float]     = {'critical': 10, 'high': 5, 'medium': 3, 'low': 1}
TIER_ALPHA: Dict[str, float] = {'critical': 0.95, 'high': 0.60, 'medium': 0.40, 'low': 0.00}

# Discrete action levels per feeder  (fraction of per-feeder demand)
ACTION_LEVELS = [0.0, 0.50, 1.0]


# ================================================================== #
#  Gymnasium Environment                                              #
# ================================================================== #
class LoadSheddingEnv:
    """
    Custom Gymnasium-compatible environment for load-shedding scheduling.

    Observation vector (per thesis Chapter 4.4.2):
        [d_1 … d_n,          normalised feeder demands
         w_1 … w_n,          priority weights (normalised)
         supply_ratio,        S / sum(d_i)
         sin(2π*t/24),        cyclic time-of-day
         cos(2π*t/24)]

    Action:
        MultiDiscrete([len(ACTION_LEVELS)] * n_feeders)
        Each component selects the allocation fraction for one feeder.
    """

    metadata = {'render_modes': []}

    def __init__(self, feeders: List[Dict], total_supply: float, n_hours: int = 24):
        """
        Parameters
        ----------
        feeders      : list of dicts with keys name, priority, demand
        total_supply : total available MW for the scheduling horizon
        n_hours      : number of time-steps per episode
        """
        try:
            import gymnasium as gym
            from gymnasium import spaces
        except ImportError:
            raise ImportError(
                "Please install gymnasium:  pip install gymnasium"
            )

        self._gym   = gym
        self._spaces = spaces

        self.feeders      = feeders
        self.total_supply = total_supply
        self.n_hours      = n_hours
        self.n_feeders    = len(feeders)
        self.current_step = 0

        # Pre-compute normalised weights
        max_w = max(TIER_W.values())
        self._weights = np.array(
            [TIER_W.get(f['priority'], 1) / max_w for f in feeders], dtype=np.float32
        )
        self._demands = np.array(
            [f.get('demand', 10.0) for f in feeders], dtype=np.float32
        )
        self._alphas = np.array(
            [TIER_ALPHA.get(f['priority'], 0.0) for f in feeders], dtype=np.float32
        )

        total_demand = self._demands.sum() or 1.0

        # Observation space
        obs_dim = self.n_feeders * 2 + 3   # demands + weights + supply_ratio + sin + cos
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(obs_dim,), dtype=np.float32
        )
        # Action space
        self.action_space = spaces.MultiDiscrete(
            [len(ACTION_LEVELS)] * self.n_feeders
        )

    # ------------------------------------------------------------------
    def _get_obs(self) -> np.ndarray:
        t = self.current_step % 24
        demand_norm  = self._demands / (self._demands.sum() or 1.0)
        supply_ratio = min(1.0, self.total_supply / (self._demands.sum() or 1.0))
        sin_t = math.sin(2 * math.pi * t / 24)
        cos_t = math.cos(2 * math.pi * t / 24)
        obs = np.concatenate([
            demand_norm.astype(np.float32),
            self._weights.astype(np.float32),
            [supply_ratio, (sin_t + 1) / 2, (cos_t + 1) / 2],
        ]).astype(np.float32)
        return obs

    def reset(self, *, seed=None, options=None):
        self.current_step = 0
        return self._get_obs(), {}

    def step(self, action):
        # Map discrete action -> allocation fractions
        fracs       = np.array([ACTION_LEVELS[a] for a in action], dtype=np.float32)
        allocations = fracs * self._demands

        # Clip to available supply
        total_alloc = allocations.sum()
        if total_alloc > self.total_supply:
            scale       = self.total_supply / total_alloc
            allocations = allocations * scale

        # ---- reward ----
        reward = 0.0
        for i, f in enumerate(self.feeders):
            ratio = allocations[i] / (self._demands[i] or 1.0)
            w     = TIER_W.get(f['priority'], 1)
            alpha = TIER_ALPHA.get(f['priority'], 0.0)

            # Priority-serving reward
            reward += w * ratio

            # Penalty for violating minimum service ratio
            if ratio < alpha:
                shortfall = alpha - ratio
                if f['priority'] == 'critical':
                    reward -= 20.0 * shortfall    # large penalty for hospital outage
                elif f['priority'] == 'high':
                    reward -= 10.0 * shortfall
                else:
                    reward -= 2.0 * shortfall

        # Fairness bonus
        reward += 5.0 * _jains_index(allocations, self._demands)

        # Over-generation penalty
        over = max(0.0, total_alloc - self.total_supply)
        reward -= 3.0 * (over / (self.total_supply or 1.0))

        self.current_step += 1
        terminated = self.current_step >= self.n_hours
        return self._get_obs(), reward, terminated, False, {}

    def render(self):
        pass


# ================================================================== #
#  RLScheduler — training and inference wrapper                      #
# ================================================================== #
class RLScheduler:
    """
    Wraps the LoadSheddingEnv with a PPO agent from stable-baselines3.

    Usage
    -----
        scheduler = RLScheduler(feeders, total_supply=60.0)
        scheduler.train(n_episodes=100)
        result = scheduler.generate_schedule(hours=list(range(24)))
    """

    def __init__(self, feeders: List[Dict], total_supply: float, n_hours: int = 24):
        self.feeders      = feeders
        self.total_supply = total_supply
        self.n_hours      = n_hours
        self.model        = None
        self.env          = None

    # ------------------------------------------------------------------
    def train(self, n_episodes: int = 100, verbose: int = 0) -> Dict:
        """
        Train the PPO agent.

        Parameters
        ----------
        n_episodes : number of episodes (thesis constraint: 100 max)
        verbose    : 0 = silent, 1 = progress output

        Returns
        -------
        dict with mean_reward and training metadata
        """
        try:
            from stable_baselines3 import PPO
            from stable_baselines3.common.env_checker import check_env
        except ImportError:
            raise ImportError(
                "Install stable-baselines3:  pip install stable-baselines3"
            )

        self.env = LoadSheddingEnv(self.feeders, self.total_supply, self.n_hours)

        # Total timesteps = episodes × steps_per_episode
        total_timesteps = n_episodes * self.n_hours

        self.model = PPO(
            policy='MlpPolicy',
            env=self.env,
            learning_rate=3e-4,
            n_steps=min(total_timesteps, 512),
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
            verbose=verbose,
        )
        self.model.learn(total_timesteps=total_timesteps)
        self.model.save(RL_MODEL_PATH)
        print(f"RL policy saved to {RL_MODEL_PATH}.zip")

        # Quick evaluation
        mean_reward = self._evaluate(n_eval_episodes=5)
        return {
            'mean_reward': mean_reward,
            'n_episodes':  n_episodes,
            'policy_path': RL_MODEL_PATH + '.zip',
        }

    # ------------------------------------------------------------------
    def load(self) -> bool:
        """Load a previously trained policy from disk."""
        try:
            from stable_baselines3 import PPO
            path = RL_MODEL_PATH + '.zip'
            if not os.path.exists(path):
                return False
            self.env   = LoadSheddingEnv(self.feeders, self.total_supply, self.n_hours)
            self.model = PPO.load(RL_MODEL_PATH, env=self.env)
            print(f"RL policy loaded from {path}")
            return True
        except Exception as e:
            print(f"RL load failed: {e}")
            return False

    def model_exists(self) -> bool:
        return os.path.exists(RL_MODEL_PATH + '.zip')

    # ------------------------------------------------------------------
    def generate_schedule(self, hours: List[int]) -> Dict:
        """
        Use the trained policy to generate a load-shedding schedule.

        Parameters
        ----------
        hours : list of hours  (e.g. list(range(24)))

        Returns
        -------
        dict with keys: schedule, fairness_index, protected_pct
        """
        if self.model is None:
            if not self.load():
                raise RuntimeError("No RL policy found. Call train() first.")

        if self.env is None:
            self.env = LoadSheddingEnv(self.feeders, self.total_supply, self.n_hours)

        obs, _ = self.env.reset()
        schedule = []
        demands  = np.array([f.get('demand', 10.0) for f in self.feeders])

        for h in hours:
            action, _ = self.model.predict(obs, deterministic=True)
            fracs      = np.array([ACTION_LEVELS[a] for a in action], dtype=np.float32)
            allocations = fracs * demands
            # Clip to supply
            total = allocations.sum()
            if total > self.total_supply:
                allocations *= self.total_supply / total

            for i, f in enumerate(self.feeders):
                schedule.append({
                    'feeder':          f['name'],
                    'hour':            h,
                    'allocated_power': float(allocations[i]),
                    'priority':        f['priority'],
                })
            obs, _, terminated, _, _ = self.env.step(action)
            if terminated:
                obs, _ = self.env.reset()

        # Compute summary metrics
        alloc_map: Dict[str, float] = {}
        for item in schedule:
            alloc_map[item['feeder']] = alloc_map.get(item['feeder'], 0.0) + item['allocated_power']

        alloc_arr = np.array([alloc_map.get(f['name'], 0.0) for f in self.feeders])
        fi        = _jains_index(alloc_arr, demands)

        crit_demand = sum(f.get('demand', 0) for f in self.feeders if f['priority'] in ('critical', 'high'))
        crit_served = sum(
            alloc_map.get(f['name'], 0)
            for f in self.feeders if f['priority'] in ('critical', 'high')
        )
        protected_pct = (crit_served / crit_demand * 100) if crit_demand > 0 else 100.0

        return {
            'schedule':        schedule,
            'fairness_index':  fi,
            'protected_pct':   protected_pct,
            'status':          'Optimal',
        }

    # ------------------------------------------------------------------
    def _evaluate(self, n_eval_episodes: int = 5) -> float:
        if self.model is None or self.env is None:
            return 0.0
        rewards = []
        for _ in range(n_eval_episodes):
            obs, _ = self.env.reset()
            ep_reward = 0.0
            done = False
            while not done:
                action, _ = self.model.predict(obs, deterministic=True)
                obs, r, terminated, truncated, _ = self.env.step(action)
                ep_reward += r
                done = terminated or truncated
            rewards.append(ep_reward)
        return float(np.mean(rewards))


# ================================================================== #
#  Utility                                                            #
# ================================================================== #
def _jains_index(allocations: np.ndarray, demands: np.ndarray) -> float:
    """Jain's Fairness Index on allocation/demand ratios."""
    ratios = np.where(demands > 0, allocations / demands, 0.0)
    s, s2, n = ratios.sum(), (ratios ** 2).sum(), len(ratios)
    return float((s ** 2) / (n * s2)) if s2 > 0 and n > 0 else 0.0
