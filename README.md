# DAVYD Dataset Studio

![DAVYD](DAVYD_SM.jpg)

DAVYD is a desktop AI dataset studio for designing schemas, generating structured synthetic records with real model providers, reviewing data quality, refining generated data, and exporting datasets for downstream AI, testing, analytics, and development workflows.

The current application is a native **PySide6 desktop app**. The old browser-first launcher is no longer part of the supported runtime.

## Who DAVYD is for

DAVYD is for people who need **controlled, structured synthetic data without rebuilding a one-off generation script for every dataset**.

- **AI and machine-learning engineers** who need labeled examples for classification, routing, extraction, evaluation, or prototype training workflows.
- **Data scientists and analysts** who need realistic structured data to develop notebooks, reports, dashboards, and transformations before a production dataset is available.
- **Software and QA engineers** who need repeatable test fixtures with realistic combinations of statuses, categories, numbers, dates, booleans, and text.
- **Product teams and application developers** who need representative records for prototypes, demos, search experiences, admin tools, or data-heavy UI states without hand-authoring every row.
- **Researchers and educators** who need reproducible schema-driven datasets for experiments, demonstrations, and coursework.
- **Teams that prefer local generation** can use Ollama instead of a hosted model provider when they want the generation step to remain on their own machine.

DAVYD is intentionally focused on **synthetic structured dataset generation and inspection**. It is not trying to replace a data warehouse, ETL platform, production database, or human annotation system.

## Real-world use cases

### Build an intent and sentiment dataset for a support model

Define fields such as:

```text
customer_message
intent
sentiment
priority
response_time_minutes
resolved
```

Generate records with a configured model, watch validated batches arrive, inspect whether categories are balanced enough for the intended experiment, edit bad rows, and export the result to CSV, JSON, Parquet, or Excel for a classifier, routing model, evaluation harness, or notebook.

This is the same kind of support dataset used in DAVYD's current documentation screenshots.

### Generate realistic QA fixtures for an application

Create a schema for records such as orders, subscriptions, tickets, accounts, or transactions, then describe the states and constraints you need to exercise. DAVYD can generate the structured rows, suppress duplicate records, and let you inspect or correct them before export.

This is useful when a test environment needs believable combinations such as:

```text
order_status = shipped | delayed | cancelled
payment_status = paid | pending | refunded
priority = low | medium | high
is_verified = true | false
amount = numeric value
created_at = datetime
```

Instead of maintaining a pile of hand-written fixture files, the schema becomes the reusable definition for creating new test data.

### Prototype a data pipeline before production data exists

When an application or analytics pipeline already has a target schema but the real dataset is not ready, DAVYD can create representative records in that shape. Export the result into the format your downstream tooling expects and use it to exercise parsing, validation, transformation, storage, visualization, or import logic.

### Create structured examples for model evaluation

Define the fields an evaluation needs, for example an input, expected category, scenario, difficulty, or other structured metadata. DAVYD provides a repeatable workflow for generating candidate examples, reviewing the dataset for missing values and duplicates, refining individual rows, and exporting the final set into an evaluation pipeline.

Synthetic examples still require domain review before they are treated as ground truth. DAVYD helps produce and inspect the dataset; it does not automatically make generated labels authoritative.

### Generate locally with Ollama

DAVYD does not require a hosted AI service. A local Ollama model can be selected through the same provider workflow, which is useful for development environments where the generation step should stay on the local machine.

## DAVYD in action

![DAVYD Dataset Studio desktop overview](docs/images/app-overview.png)

The screenshots in this repository are captured from the real desktop application. The populated views use a deterministic documentation fixture to exercise DAVYD's production Schema, Generate, and Data & Quality UI without embedding provider credentials or representing the fixture rows as provider-generated output.

**[Open the full visual walkthrough →](docs/APP_WALKTHROUGH.md)**

## What DAVYD does

DAVYD provides one end-to-end desktop workflow:

1. **Schema**: define field names, types, descriptions, examples, and constraints.
2. **Generate**: choose a provider/model, generation quality, row count, and batch size.
3. **Stream**: watch validated rows arrive batch-by-batch while generation is running.
4. **Refine**: edit generated cells and use undo/redo without losing the canonical dataset state.
5. **Inspect**: search the active rows, review completeness and duplicates, inspect field health, and use guided visual insights for distributions, top values, relationships, and missingness.
6. **Export**: save CSV, JSON, Parquet, or Excel output depending on the active workflow.

Generation is exact-row oriented: DAVYD validates model output against the schema, suppresses duplicate rows, retries invalid batches, reports progress, and supports cooperative cancellation.

## Desktop workspaces

### Schema

The Schema workspace is the definition authority for generated data. It feeds the active schema into both generation and quality views.

![DAVYD Schema workspace](docs/images/schema-workspace.png)

### Generate

The Generate workspace provides:

- streamed batch delivery;
- live row and progress counters;
- editable generated cells;
- undo and redo history;
- CSV, JSON, Parquet, and Excel export;
- cancellation through the desktop shell.

![DAVYD generation workspace streaming validated rows](docs/images/generation-live.png)

`MainWindow` is the single generation orchestrator. Provider work runs on a Qt worker thread and reports only through signals. Closing DAVYD during generation requests cooperative cancellation and waits for the worker thread to finish before the application tears down its Qt objects.

### Data & Quality

The Data & Quality workspace provides:

- searchable data preview;
- row, column, completeness, and duplicate health cards;
- automatic field-aware visual insights;
- numeric distributions with median and range context;
- readable ranked top-value views for categorical data;
- numeric relationship views with correlation context;
- field-level missingness inspection;
- field health summaries covering type, completeness, unique values, and representative values or numeric ranges.

![DAVYD Data & Quality workspace](docs/images/data-quality.png)

Search filters drive both the preview and active visual insight, so the chart describes the same rows the user is inspecting. Edits made in Generate remain authoritative for subsequent Save operations and are refreshed into Data & Quality when that workspace is opened.

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
