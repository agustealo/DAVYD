# DAVYD Dataset Studio

![DAVYD](DAVYD_SM.jpg)

DAVYD is a desktop AI dataset studio for designing schemas, generating synthetic records with real model providers, reviewing data quality, refining generated data, and exporting production-ready datasets.

The current application is a native **PySide6 desktop app**. The old browser-first launcher is no longer part of the supported runtime.

## What DAVYD does

DAVYD provides one end-to-end desktop workflow:

1. **Schema**: define field names, types, descriptions, examples, and constraints.
2. **Generate**: choose a provider/model, generation quality, row count, and batch size.
3. **Stream**: watch validated rows arrive batch-by-batch while generation is running.
4. **Refine**: edit generated cells and use undo/redo without losing the canonical dataset state.
5. **Inspect**: search the dataset, review missing/duplicate counts, profile columns, and draw native charts.
6. **Export**: save CSV, JSON, Parquet, or Excel output depending on the active workflow.

Generation is exact-row oriented: DAVYD validates model output against the schema, suppresses duplicate rows, retries invalid batches, reports progress, and supports cooperative cancellation.

## Desktop workspaces

### Schema

The Schema workspace is the definition authority for generated data. It feeds the active schema into both generation and quality views.

### Generate

The Generate workspace provides:

- streamed batch delivery;
- live row and progress counters;
- editable generated cells;
- undo and redo history;
- CSV, JSON, Parquet, and Excel export;
- cancellation through the desktop shell.

`MainWindow` is the single generation orchestrator. Provider work runs on a Qt worker thread and reports only through signals. Closing DAVYD during generation requests cooperative cancellation and waits for the worker thread to finish before the application tears down its Qt objects.

### Data & Quality

The Data & Quality workspace provides:

- dataset search;
- row and column counts;
- missing-value and duplicate counts;
- per-column type, missing, unique, and example profiling;
- histogram, bar, and scatter charts rendered natively with Matplotlib.

Edits made in Generate remain authoritative for subsequent Save operations and are refreshed into Data & Quality when that workspace is opened.

## Supported model providers

DAVYD currently exposes these provider identifiers through the canonical provider registry:

- Ollama
- OpenAI
- ChatGPT compatibility alias
- DeepSeek
- Gemini
- Anthropic
- Claude compatibility alias
- Mistral
- Groq
- Hugging Face

Model discovery and connection checks occur only after an explicit user action. DAVYD does not make provider calls simply because the application started.

## Requirements

- Python **3.12, 3.13, or 3.14**
- Git for source installs
- A supported operating system for PySide6: macOS, Windows, or Linux
- A local Ollama installation when using Ollama, or valid credentials for hosted providers

## Install from source

```bash
git clone https://github.com/agustealo/DAVYD.git
cd DAVYD
python -m venv .venv
```

Activate the environment.

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install DAVYD:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

Launch the desktop application:

```bash
davyd
```

You can also run the Python entry point directly:

```bash
python src/ui_desktop.py
```

## Credentials and provider configuration

DAVYD does **not** write provider credentials to its JSON settings file.

For hosted providers, credential resolution is:

1. `DAVYD_<PROVIDER>_API_KEY`, for example `DAVYD_OPENAI_API_KEY`;
2. `DAVYD_API_KEY`;
3. the operating-system credential vault through Python `keyring`.

A credential entered in the desktop sidebar is stored in the OS vault when secure storage is available. If the vault is unavailable, DAVYD uses the value for the current session instead of silently writing it to plaintext settings.

For Ollama, the credential field can contain an Ollama host URL such as `http://127.0.0.1:11434`.

See [SECURITY.md](SECURITY.md) for the repository credential policy and the required response to the credential historically committed by older revisions of DAVYD.

## Application data locations

DAVYD keeps runtime data outside the source tree.

### macOS

- Data: `~/Library/Application Support/DAVYD`
- Logs: `~/Library/Logs/DAVYD`

### Windows

- Data: `%LOCALAPPDATA%\DAVYD`
- Logs: `%LOCALAPPDATA%\DAVYD\logs`

### Linux

- Data: `$XDG_DATA_HOME/davyd`, or `~/.local/share/davyd`
- Logs: `$XDG_STATE_HOME/davyd/logs`, or `~/.local/state/davyd/logs`

Local settings and generated runtime data are excluded from source control.

## Development

Install the development dependency set:

```bash
python -m pip install -e '.[dev]'
```

Run the generation contracts:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_generation_contract.py -q
```

Compile the source tree:

```bash
python -m compileall -q src
```

The GitHub Actions modernization gate intentionally separates two contracts:

- **generation-contract** validates the generation engine without third-party Qt pytest plugins bleeding into the environment;
- **desktop-shell** provisions the Linux Qt runtime, imports the desktop modules, and constructs a real offscreen `MainWindow`.

This split keeps generation failures distinguishable from desktop runtime failures.

## Architecture

The supported desktop path is intentionally small and canonical:

```text
ui_desktop.py
    |
    v
MainWindow
    |-- Sidebar
    |-- TabsManager
    |     |-- Schema
    |     |-- Generate
    |     `-- Data & Quality
    |
    `-- DatasetGenerationWorker
            |
            v
      DatasetGenerator
            |
            v
   ModelProviderRegistry
            |
            v
      model_providers
```

Configuration, credential storage, generation, provider selection, dataset persistence, and UI orchestration each have one primary authority. New functionality should extend those authorities rather than creating parallel execution paths.

## Repository security

Do not commit:

- API keys or access tokens;
- local `settings.json` files;
- generated datasets;
- logs;
- virtual environments;
- build artifacts or caches.

A credential that existed in repository history must be considered compromised until it is revoked and the affected history has been remediated. Deleting the current file is not sufficient by itself.

## License

DAVYD is released under the [MIT License](LICENSE).

## Project

- Repository: https://github.com/agustealo/DAVYD
- Developer site: https://agustealo.com
