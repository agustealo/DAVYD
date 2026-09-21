# DAVYD Dataset Studio · Visual Walkthrough

These captures are rendered from the current PySide6 desktop application. They document the supported consumer workflow rather than a separate design mockup.

The populated screenshots use a deterministic support-dataset documentation fixture to exercise DAVYD's real schema, streaming table, progress, profiling, search, and insight UI without embedding provider credentials or claiming that a hosted model produced the pictured rows.

## Application overview

![DAVYD Dataset Studio overview](images/app-overview.png)

DAVYD opens as one desktop workspace with persistent generation controls on the left and three canonical workspaces on the right: **Schema**, **Generate**, and **Data & Quality**. Provider/model selection, dataset size, quality, and batch controls remain available without triggering network calls simply because the application opened.

## 1. Define the schema

![DAVYD Schema workspace](images/schema-workspace.png)

The **Schema** workspace is the definition authority for generated records. Each field carries a name, type, description, required flag, and example. Schema changes are propagated to the Generate and Data & Quality workspaces through the existing desktop signal flow.

The screenshot shows a customer-support schema with text, categorical, numeric, and boolean fields. This is documentation data only; the schema editor shown is the real application UI.

## 2. Watch generation stream into the workspace

![DAVYD generation in action](images/generation-live.png)

The **Generate** workspace is shown mid-run at 67% with validated rows already streamed into the editable table. The live UI exposes:

- generation state and progress;
- current row and batch counts;
- the generated table as batches arrive;
- undo and redo controls for post-generation editing;
- export access;
- a compact generation log.

For this capture, the documentation fixture is sent through `GenerationTab`'s real batch queue, flush, progress, and table-rendering methods. A normal user run reaches the same UI through `DatasetGenerationWorker` and the configured model provider.

## 3. Explore data quality and useful insights

![DAVYD Data & Quality workspace](images/data-quality.png)

The redesigned **Data & Quality** workspace is built around decisions rather than raw chart mechanics. It combines a searchable row preview with four at-a-glance health cards, a guided visual explorer, plain-language chart takeaways, and a compact field-health table.

The visual explorer provides five user-facing insight modes:

- **Auto insight** chooses a useful view from the selected field type;
- **Distribution** shows numeric shape, range, and median;
- **Top values** ranks categorical or text values with readable horizontal bars and count labels;
- **Relationship** compares two numeric fields and reports correlation with a descriptive trend line;
- **Missingness** surfaces incomplete fields as percentages, or explicitly confirms when the current rows are complete.

The screenshot focuses on the `priority` field. Instead of a cramped generic bar chart, DAVYD ranks the values horizontally and explains the dominant value and its share below the visual. Search filters update both the row preview and the active insight so the visual always reflects the rows currently being inspected.

The **Field health** section reports field kind, completeness percentage, unique-value count, and a useful typical-value or numeric-range summary. This makes sparse, overly unique, or suspicious fields easier to spot without reading a raw profiling dump.

## Supported user flow

```text
Schema
  ↓
Generate with a configured provider/model
  ↓
Stream validated batches + progress
  ↓
Edit / undo / redo
  ↓
Data & Quality inspection
  ↓
Export CSV / JSON / Parquet / Excel
```

`MainWindow` remains the single generation orchestrator. Provider work runs through the Qt worker path, generated edits remain canonical, and Data & Quality refreshes from that current dataset when opened.

## Screenshot provenance

The PNGs in `docs/images/` are captured from the real application at 1500 × 940 using Qt's own window capture after constructing `MainWindow`, `MenuBar`, and the production theme. The Data & Quality capture also exercises Top values, Distribution, and Missingness behavior before the image is accepted. The capture run verifies that the PNG is non-empty before committing it to the repository.
