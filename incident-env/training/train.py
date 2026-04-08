from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from datetime import datetime

import torch
from torch import nn
from torch.distributions import Categorical
from torch.utils.tensorboard import SummaryWriter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from tests.mock_env import MockIncidentEnv
from training.curriculum import CurriculumScheduler


@dataclass
class HyperParams:
	lr: float = 3e-4
	gamma: float = 0.99
	clip_epsilon: float = 0.2
	value_coef: float = 0.5
	entropy_coef: float = 0.01


class ActorCritic(nn.Module):
	def __init__(self, obs_dim: int = 72):
		super().__init__()
		self.shared = nn.Sequential(
			nn.Linear(obs_dim, 256),
			nn.Tanh(),
			nn.Linear(256, 128),
			nn.Tanh(),
		)
		self.service_head = nn.Linear(128, 12)
		self.action_head = nn.Linear(128, 7)
		self.value_head = nn.Linear(128, 1)

	def forward(self, obs: torch.Tensor):
		h = self.shared(obs)
		return self.service_head(h), self.action_head(h), self.value_head(h).squeeze(-1)


def collect_rollout(env: MockIncidentEnv, model: ActorCritic, rollout_steps: int, device: torch.device):
	obs_np, _ = env.reset()
	obs = torch.tensor(obs_np, dtype=torch.float32, device=device)

	obs_buf, svc_buf, act_buf = [], [], []
	logp_buf, rew_buf, done_buf, val_buf = [], [], [], []

	for _ in range(rollout_steps):
		svc_logits, act_logits, value = model(obs.unsqueeze(0))
		svc_dist = Categorical(logits=svc_logits)
		act_dist = Categorical(logits=act_logits)

		service = svc_dist.sample().squeeze(0)
		action = act_dist.sample().squeeze(0)
		log_prob = svc_dist.log_prob(service) + act_dist.log_prob(action)

		next_obs_np, reward, terminated, truncated, _ = env.step([int(service.item()), int(action.item())])
		done = terminated or truncated

		obs_buf.append(obs)
		svc_buf.append(service)
		act_buf.append(action)
		logp_buf.append(log_prob)
		rew_buf.append(torch.tensor(float(reward), dtype=torch.float32, device=device))
		done_buf.append(torch.tensor(float(done), dtype=torch.float32, device=device))
		val_buf.append(value.squeeze(0))

		if done:
			next_obs_np, _ = env.reset()
		obs = torch.tensor(next_obs_np, dtype=torch.float32, device=device)

	with torch.no_grad():
		_, _, last_val = model(obs.unsqueeze(0))
		last_val = last_val.squeeze(0)

	return {
		"obs": torch.stack(obs_buf),
		"service": torch.stack(svc_buf),
		"action": torch.stack(act_buf),
		"old_logp": torch.stack(logp_buf),
		"reward": torch.stack(rew_buf),
		"done": torch.stack(done_buf),
		"value": torch.stack(val_buf),
		"last_val": last_val,
	}


def compute_returns(rewards, dones, last_val, gamma):
	returns = []
	ret = last_val
	for idx in range(len(rewards) - 1, -1, -1):
		ret = rewards[idx] + gamma * ret * (1.0 - dones[idx])
		returns.append(ret)
	returns.reverse()
	return torch.stack(returns)


def ppo_update(batch, model, optimizer, hp: HyperParams):
	returns = compute_returns(batch["reward"], batch["done"], batch["last_val"], hp.gamma)
	advantages = returns - batch["value"]
	advantages = (advantages - advantages.mean()) / (advantages.std().clamp_min(1e-6))

	svc_logits, act_logits, values = model(batch["obs"])
	svc_dist = Categorical(logits=svc_logits)
	act_dist = Categorical(logits=act_logits)

	new_logp = svc_dist.log_prob(batch["service"]) + act_dist.log_prob(batch["action"])
	entropy = svc_dist.entropy().mean() + act_dist.entropy().mean()

	ratio = (new_logp - batch["old_logp"]).exp()
	surr1 = ratio * advantages
	surr2 = torch.clamp(ratio, 1 - hp.clip_epsilon, 1 + hp.clip_epsilon) * advantages

	actor_loss = -torch.min(surr1, surr2).mean()
	critic_loss = torch.mean((returns - values) ** 2)
	loss = actor_loss + hp.value_coef * critic_loss - hp.entropy_coef * entropy

	optimizer.zero_grad()
	loss.backward()
	nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.5)
	optimizer.step()

	return {
		"loss": float(loss.item()),
		"actor_loss": float(actor_loss.item()),
		"critic_loss": float(critic_loss.item()),
		"entropy": float(entropy.item()),
		"mean_reward": float(batch["reward"].mean().item()),
	}


def save_checkpoint(model: ActorCritic, optimizer, epoch: int, curriculum_level: int, checkpoint_dir: Path):
	"""Save model checkpoint to disk."""
	checkpoint_dir.mkdir(parents=True, exist_ok=True)
	checkpoint_path = checkpoint_dir / f"checkpoint_epoch_{epoch}_level_{curriculum_level}.pt"
	
	torch.save({
		"epoch": epoch,
		"model_state_dict": model.state_dict(),
		"optimizer_state_dict": optimizer.state_dict(),
		"curriculum_level": curriculum_level,
	}, checkpoint_path)
	
	# Also save as "latest" for easy loading
	latest_path = checkpoint_dir / "latest.pt"
	torch.save({
		"epoch": epoch,
		"model_state_dict": model.state_dict(),
		"optimizer_state_dict": optimizer.state_dict(),
		"curriculum_level": curriculum_level,
	}, latest_path)
	
	print(f"Checkpoint saved: {checkpoint_path.name}")


def main():
	parser = argparse.ArgumentParser(description="Track B PPO bootstrap trainer")
	parser.add_argument("--epochs", type=int, default=1000)
	parser.add_argument("--rollout-steps", type=int, default=256)
	parser.add_argument("--checkpoint-interval", type=int, default=100)
	parser.add_argument("--log-dir", type=str, default="logs")
	parser.add_argument("--checkpoint-dir", type=str, default="checkpoints")
	args = parser.parse_args()

	device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
	print(f"Using device: {device}")
	
	hp = HyperParams()
	env = MockIncidentEnv(max_steps=30, seed=42)
	model = ActorCritic().to(device)
	optimizer = torch.optim.Adam(model.parameters(), lr=hp.lr)
	scheduler = CurriculumScheduler()

	# Setup TensorBoard
	log_dir = Path(args.log_dir) / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
	writer = SummaryWriter(log_dir=str(log_dir))
	checkpoint_dir = Path(args.checkpoint_dir)
	
	print(f"Starting training on MockIncidentEnv")
	print(f"TensorBoard logs: {log_dir}")
	print(f"Checkpoints: {checkpoint_dir}")
	print(f"Hyperparameters: lr={hp.lr}, gamma={hp.gamma}, clip_epsilon={hp.clip_epsilon}")
	
	for epoch in range(1, args.epochs + 1):
		batch = collect_rollout(env, model, args.rollout_steps, device)
		metrics = ppo_update(batch, model, optimizer, hp)

		# Log to TensorBoard
		writer.add_scalar("Loss/total", metrics["loss"], epoch)
		writer.add_scalar("Loss/actor", metrics["actor_loss"], epoch)
		writer.add_scalar("Loss/critic", metrics["critic_loss"], epoch)
		writer.add_scalar("Metrics/entropy", metrics["entropy"], epoch)
		writer.add_scalar("Metrics/mean_reward", metrics["mean_reward"], epoch)
		writer.add_scalar("Curriculum/level", scheduler.current_level, epoch)

		# Check curriculum advancement
		advanced = scheduler.update(metrics["mean_reward"])
		if advanced:
			print(f"🎓 Curriculum advanced to level {scheduler.current_level}")
			writer.add_scalar("Curriculum/advancement", scheduler.current_level, epoch)
		
		# Console output
		if epoch % 10 == 0 or advanced:
			print(
				f"epoch={epoch}/{args.epochs} | "
				f"loss={metrics['loss']:.4f} | "
				f"reward={metrics['mean_reward']:.4f} | "
				f"entropy={metrics['entropy']:.4f} | "
				f"level={scheduler.current_level}"
			)

		# Save checkpoint periodically
		if epoch % args.checkpoint_interval == 0:
			save_checkpoint(model, optimizer, epoch, scheduler.current_level, checkpoint_dir)

	# Save final checkpoint
	save_checkpoint(model, optimizer, args.epochs, scheduler.current_level, checkpoint_dir)
	writer.close()
	print(f"✅ Training complete! Final level: {scheduler.current_level}")


if __name__ == "__main__":
	main()
