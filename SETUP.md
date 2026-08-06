# Development setup

The project supports Python 3.10 or newer and has one runtime dependency,
PyYAML. Pytest is included in the optional `dev` dependency group.

## Clone and install

```bash
git clone https://github.com/beastofbayarea/financial-wellness-lab.git
cd financial-wellness-lab
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On Windows PowerShell, replace the activation command with:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks local activation scripts, the environment can still be
used without activation:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

## Verify the checkout

Run the complete suite and both executable examples from the repository root:

```bash
python -m pytest
python -m eligibility.demo
python -m card_economics.compare
```

Launch the combined dashboard:

```bash
streamlit run dashboard.py
```

Streamlit prints the local address (normally `http://localhost:8501`) and opens
it in the default browser. Stop the server with `Ctrl+C`.

The examples and dashboard work offline and use deterministic fallback text
when narration is unavailable.

## Optional narration

Set `ANTHROPIC_API_KEY` to allow `shared/narrator.py` to call Anthropic's
Messages API using the model configured in that module. This is optional: API
availability never changes an eligibility decision or an economic calculation.

```bash
export ANTHROPIC_API_KEY="your-key"
```

```powershell
$env:ANTHROPIC_API_KEY = "your-key"
```

Do not commit API keys or local environment files. The code does not load a
`.env` file automatically.

## Editing assumptions

- Eligibility thresholds and limits: `eligibility/rules_config.yaml`
- Card portfolio, revenue, path, and walk-away assumptions:
  `card_economics/assumptions.yaml`

Configuration is loaded when the relevant module is imported or executed.
Restart a Python process after changing eligibility configuration.
