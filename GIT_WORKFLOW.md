# Git Workflow — IncidentEnv
> Collaboration guide for 2-person 48-hour hackathon

---

## Branch Strategy

```
main            ← always runnable, merge at milestones only
feat/track-a    ← Person A's branch
feat/track-b    ← Person B's branch
```

## Initial Setup (Both people do this once)

```bash
# Clone and create your branch
git clone <repo-url>
cd incident-env

# Person A:
git checkout -b feat/track-a

# Person B:
git checkout -b feat/track-b
```

## Commit Message Format

```
[A] feat: Rust service graph propagation logic
[B] feat: PPO training loop with curriculum
[A] fix: PyO3 binding for step() return tuple
[B] fix: WebSocket disconnect handling
[BOTH] chore: integration milestone 2 complete
[A] test: all 4 test files passing
[B] docs: update trackB progress
```

## Sync Points (Merge to main at each milestone)

```bash
# Person A merges at Milestone 1 (Hour 8):
git checkout main
git merge feat/track-a
git push origin main

# Person B pulls:
git pull origin main
git merge main feat/track-b
```

## The Rule: Never Break Main

- Test locally before merging to main
- If in doubt, commit to your branch and tell the other person
- Broken main = both people blocked

## Conflict Zones (Files both people touch)

| File | Rule |
|---|---|
| `API_CONTRACT.md` | Discuss before changing. Both commit together. |
| `trackA.md` / `trackB.md` | Each person owns their own file only |
| `pyproject.toml` | Discuss before adding deps |
| `tests/` | A owns test_*.py, B owns mock_env.py |

## .gitignore Must Include

```
.venv/
target/
checkpoints/
logs/
*.pth
*.pt
__pycache__/
.env
node_modules/
dashboard/dist/
```
