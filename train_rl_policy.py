"""
train_rl_policy.py — Run this ONCE before the viva to pre-train and save the RL policy.

Usage:
    python train_rl_policy.py

This takes ~2–5 minutes. The output file  models/rl_policy.zip  is then loaded
automatically by the application — no live training needed during demos.
"""

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)

from config import RL_POLICY_PATH, RL_TOTAL_TIMESTEPS

DEMO_FEEDERS = [
    {"name": "Civil Hospital Feeder",      "priority": "critical", "demand": 8.0},
    {"name": "Rohri Industrial Feeder",    "priority": "high",     "demand": 18.0},
    {"name": "Airport Road Feeder",        "priority": "high",     "demand": 14.0},
    {"name": "Military Road Feeder",       "priority": "medium",   "demand": 12.0},
    {"name": "SITE Area Feeder",           "priority": "medium",   "demand": 16.0},
    {"name": "Barrage Colony Feeder",      "priority": "low",      "demand": 10.0},
    {"name": "Shikarpur Road Feeder",      "priority": "low",      "demand": 9.0},
    {"name": "Sukkur City Centre Feeder",  "priority": "low",      "demand": 11.0},
]
TOTAL_SUPPLY = 75.0  # MW — less than sum(demand)=98 to force realistic shedding


def main():
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.env_checker import check_env
    except ImportError:
        logger.error("stable-baselines3 not installed. Run:  pip install stable-baselines3 gymnasium")
        return

    from core.rl_scheduler import LoadSheddingEnv

    logger.info("Building environment …")
    env = LoadSheddingEnv(feeders=DEMO_FEEDERS, total_supply=TOTAL_SUPPLY, n_hours=24)

    logger.info("Training PPO for %d timesteps …", RL_TOTAL_TIMESTEPS)
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        n_steps=512,
        batch_size=64,
        n_epochs=10,
        learning_rate=3e-4,
        gamma=0.99,
        clip_range=0.2,
        ent_coef=0.01,
    )
    model.learn(total_timesteps=RL_TOTAL_TIMESTEPS, progress_bar=True)

    model.save(RL_POLICY_PATH.replace(".zip", ""))
    logger.info("Policy saved to %s", RL_POLICY_PATH)
    logger.info("Done — the application will now load this policy automatically.")


if __name__ == "__main__":
    main()
