# Week 1 (Beginner-Friendly) - Start Here

Welcome. Week 1 is designed so you can make real progress even if you are new to ML, data science, or AI.

You will pick one role, follow one guide, and finish one clear set of tasks.

## Start in 15 minutes

If you are totally new, run these commands first:

```bash
git clone https://github.com/sanjana-garimella/MediRare
cd MediRare
git fetch --all
git switch week1/<your-role>
python scripts/week1_check.py --role <role>
```

Expected outcome:
- You are **not** on `main`.
- The script prints mostly `[OK]` lines.
- If you see `[FAIL]`, follow the troubleshooting section below.

## What you will do this week

- Choose one role and work only on that branch.
- Set up Python and minimal dependencies.
- Use starter files or scripts to produce working outputs.
- Validate the result and commit on your branch, not `main`.

You do **not** need to build a full AI model in Week 1.

## What you will learn

- Why clean data formats and branch discipline matter.
- How reproducible workflows help research projects.
- How each role contributes to the overall pipeline.

## One Rule That Matters

Do **not** commit to `main`.

Create and work on **only one** of these branches:

- `week1/nlp`
- `week1/biomedical`
- `week1/cv`
- `week1/backend`
- `week1/integration`

## Quick Git Commands (Copy/Paste)

```bash
git clone https://github.com/sanjana-garimella/MediRare
cd MediRare

# Get the latest branches from GitHub
git fetch --all

# Pick ONE branch name from the list above and switch to it
git switch week1/<your-role>

git branch --show-current
```

If `git switch week1/<your-role>` fails, ask for help (it usually means the branch does not exist on GitHub yet).

## Troubleshooting (Common First-Day Issues)

- `python: command not found`
  - Try `python3 --version`
  - If it works, use `python3` instead of `python` in all commands.
- `git switch week1/<your-role>` fails
  - Run `git fetch --all` and try again.
  - If it still fails, that branch may not exist yet.
- `ModuleNotFoundError` after install
  - Activate your virtual environment before running scripts:
    - macOS/Linux: `source .venv/bin/activate`
    - Windows: `.venv\Scripts\activate`
- Accidentally worked on `main`
  - Stop and switch to your Week 1 branch before committing.

## Important: What You Should Commit

Week 1 creates large generated outputs (downloaded PDFs, extracted images, downloaded XML). Do **not** commit those.

You should commit:
- your code changes (scripts)
- small text/CSV outputs that are meant to be shared (like templates)
- short notes (README) describing what you ran and what happened

## Guides

Pick one role guide and follow it end-to-end:

- [NLP Guide](./nlp.md)
- [Biomedical Guide](./biomedical.md)
- [CV Guide](./cv.md)
- [Backend Guide](./backend.md)
- [Integration Guide](./integration.md)

## General resources

- [Week 1 Learning Resources](./learning_resources.md) (friendly concept explanations + source links)

## One Command Self-Check

After you finish your role tasks, run:

```bash
python scripts/week1_check.py --role <role>
```

Examples:

```bash
python scripts/week1_check.py --role nlp
python scripts/week1_check.py --role cv
python scripts/week1_check.py --role biomedical
python scripts/week1_check.py --role backend
python scripts/week1_check.py --role integration
```

## Minimum success target (Week 1)

For Week 1, you are successful if:
- You worked on exactly one `week1/*` branch.
- You completed one role guide end-to-end.
- `python scripts/week1_check.py --role <role>` passes required checks.
- You committed role-related code/docs (not large generated data).

That is enough for a strong Week 1 submission.
