# Development setup

The project supports Python 3.10 or newer. Runtime dependencies are declared in
`pyproject.toml`; Pytest is included in the optional `dev` dependency group.

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

Run the fast smoke suite and both executable examples from the repository root:

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
it in the default browser. Use the sidebar or home-page cards to open each workflow
on its own page. Stop the server with `Ctrl+C`.

Run the full validation suite before a release or after changing domain logic:

```bash
python -m pytest eligibility card_economics tests
```

The examples and dashboard work offline and use deterministic fallback text
when narration is unavailable.

## Optional Gemini narration

The explanation layer uses the Google Gen AI SDK with Gemini on Vertex AI. Copy
the checked-in template, then keep the resulting `.env` local:

```powershell
Copy-Item .env.example .env
```

```bash
cp .env.example .env
```

The Cent-compatible defaults are:

- `GCP_PROJECT_ID=cent-capital-472820`
- `GCP_REGION=global`
- `GEMINI_MODEL=gemini-flash-latest`
- `GEMINI_MAX_TOKENS=8192`

Authentication uses Google Application Default Credentials. For local user
credentials, use `gcloud auth application-default login`. For a service
account, set `GOOGLE_APPLICATION_CREDENTIALS` to a JSON key stored outside this
repository. The project must have Vertex AI access and the authenticated
identity must be authorized to generate content.

If a deployment-only credential path is inherited on another operating system
and the file does not exist, the app safely uses the standard local gcloud ADC
file instead. It never reads or copies credentials into the repository.

The app loads `.env` automatically and gives its values precedence over settings
inherited from another project's terminal. Never commit `.env`, credential JSON,
access tokens, or private keys. If configuration or authentication is
unavailable, the LLM call returns no text and the deterministic fallback remains
available.

## Editing assumptions

- Eligibility thresholds and limits: `eligibility/rules_config.yaml`
- Card portfolio, revenue, path, and walk-away assumptions:
  `card_economics/assumptions.yaml`

Configuration is loaded when the relevant module is imported or executed.
Restart a Python process after changing eligibility configuration.
