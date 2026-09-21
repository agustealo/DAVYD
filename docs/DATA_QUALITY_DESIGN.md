# Data & Quality Interaction Model

DAVYD's Data & Quality workspace is designed around user questions rather than chart primitives.

## Information hierarchy

1. **Health cards** answer whether the dataset is broadly usable: rows, columns, completeness, and duplicate rows.
2. **Data preview** lets the user search and inspect actual records.
3. **Visual insight** explains one useful pattern at a time with readable defaults and a plain-language takeaway.
4. **Field health** summarizes type, completeness, cardinality, and a representative value or numeric range.

## Insight modes

- **Auto insight** selects a distribution for numeric fields and ranked top values for non-numeric fields.
- **Distribution** emphasizes numeric shape, median, and range.
- **Top values** uses horizontal ranking for readable category labels and shows counts directly on the bars.
- **Relationship** compares two numeric fields, reports correlation, and adds a descriptive trend line when enough data is available.
- **Missingness** ranks incomplete fields by percentage and explicitly confirms when the current rows are complete.

Search filters affect both the row preview and the active visual insight so the chart never describes a different slice than the table being inspected.

## Design principles

- Prefer plain-language tasks over visualization jargon.
- Prefer horizontal categorical charts when labels matter.
- Put the key numeric takeaway next to the visual instead of forcing users to infer it from axes.
- Keep data quality metrics visible before visualization controls.
- Avoid decorative charts that do not answer a concrete inspection question.
- Keep the implementation native to the existing PySide6 + Matplotlib desktop stack; do not introduce a second visualization runtime.
