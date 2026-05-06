# Week 1 Learning Resources

This page explains Week 1 ideas in plain language, then points you to the exact project guides and external sources.

## Why this matters

Week 1 is less about "advanced AI" and more about strong project habits:

- using one branch per role
- creating reproducible data files
- validating inputs early
- documenting what you did

These habits make your work easier to review, debug, and build on later.

## Role map (what each role means)

- `week1/backend`: defines data rules (schemas) so all teams produce compatible outputs.
- `week1/biomedical`: turns clinical language into structured annotations and HPO mappings.
- `week1/cv`: pulls figures from PDFs and records metadata for later modeling.
- `week1/nlp`: collects PubMed case report text into reusable JSONL files.
- `week1/integration`: combines mock inputs to test the end-to-end data flow.

Start guide for each role:
- `docs/week1/backend.md`
- `docs/week1/biomedical.md`
- `docs/week1/cv.md`
- `docs/week1/nlp.md`
- `docs/week1/integration.md`

## Friendly concept explanations + where to go next

### Data formats

- **JSONL**: think "one record per line." This keeps files easy to stream, validate, and debug.
  - Used in guides: `docs/week1/nlp.md`, `docs/week1/cv.md`, `docs/week1/integration.md`, `docs/week1/backend.md`
  - Learn more: https://jsonlines.org/
- **CSV**: a spreadsheet-like format that is quick for humans to edit and review.
  - Used in guide: `docs/week1/biomedical.md`
  - Learn more: https://www.w3schools.com/python/pandas/pandas_csv.asp
- **Metadata**: data *about* data (for example, figure path, source paper ID, extraction time).
  - Used in guide: `docs/week1/cv.md`

### Reproducibility

- Reproducibility means someone else can run your steps and get similar results.
- Save raw files separately from processed files so you can trace what changed.
- Use scripts and consistent paths instead of manual one-off edits.
  - Seen in guides: `docs/week1/nlp.md`, `docs/week1/cv.md`, `docs/week1/integration.md`

### Validation

- Validation is your "quality gate." It catches format and schema problems early.
- Backend checks schemas and tests; other roles benefit from cleaner handoffs.
  - Start here: `docs/week1/backend.md`
  - Self-check command reference: `docs/week1/README.md`
  - Learn more (`pytest`): https://docs.pytest.org/en/stable/getting-started.html

### Branching and collaboration

- A branch is your safe workspace. You can experiment without breaking `main`.
- Week 1 uses one role branch per student to keep work isolated and reviewable.
  - Branch workflow: `docs/week1/README.md`
  - Learn more: https://www.atlassian.com/git/tutorials/using-branches

### Biomedical context

- **PubMed** is where you find case reports and abstracts.
  - Used in guide: `docs/week1/nlp.md`, `docs/week1/biomedical.md`
  - Learn more: https://pubmed.ncbi.nlm.nih.gov/help/
- **HPO** gives standard symptom IDs so annotations are consistent.
  - Used in guide: `docs/week1/biomedical.md`
  - Learn more: https://hpo.jax.org/app/help

### Tools you will see in commands

- **venv**: project-specific Python environment (prevents dependency conflicts).
  - Learn more: https://realpython.com/python-virtual-environments/
- **pip**: installs Python packages into your current environment.
  - Learn more: https://pip.pypa.io/en/stable/user_guide/
- **Streamlit**: quick UI for data display.
  - Used in guide: `docs/week1/integration.md`
  - Learn more: https://docs.streamlit.io/
- **PyMuPDF**: reads PDFs and helps extract figure assets.
  - Used in guide: `docs/week1/cv.md`
  - Learn more: https://pymupdf.readthedocs.io/

## Suggested reading order

1. `docs/week1/README.md` (project rules + role selection)
2. your single role guide in `docs/week1/`
3. this page while doing tasks (for concepts + links)
4. external docs only when you hit something specific

## Need more help?

If you are stuck:

- Re-read your role guide step-by-step and compare expected outputs.
- Run the self-check command from `docs/week1/README.md`.
- Copy the exact error message and ask a teammate/instructor.
- Use the linked external source for the exact concept you are blocked on.
