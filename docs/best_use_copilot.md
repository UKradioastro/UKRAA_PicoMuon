# Using GitHub Copilot Effectively for PicoMuon

GitHub Copilot can help develop a high-quality, high-performance muon data
collection, processing, and display engine. It works best when used as a design
partner, code generator, reviewer, and test planner rather than as an unchecked
"write the whole system" tool.

## Recommended Project Setup

Use a project instruction file:

```text
.github/copilot-instructions.md
```

Do not rely on `.copilot/COPILOT.md` for repository guidance.

Focused instruction files can also be added when different parts of the project
need distinct guidance:

```text
.github/instructions/python.instructions.md
.github/instructions/raspberrypi.instructions.md
.github/instructions/data-pipeline.instructions.md
```

Project instructions should describe:

- The project goal: muon data collection, processing, monitoring, and plotting.
- The architecture: acquisition, validation, processing, storage, and
  visualization.
- Operating constraints: Raspberry Pi, Linux services, cron or systemd, CSV or
  log files, and limited CPU, memory, and storage.
- Coding standards: type hints, structured logging, explicit error handling,
  and appropriate tests.
- Performance expectations: streaming where practical, non-blocking or bounded
  I/O, bounded memory use, and reproducible processing.
- Scientific requirements: explicit units, reliable timestamps, calibration
  metadata, and retention of original observations.

Useful project-wide rules include:

- Prefer explicit schema validation over implicit parsing.
- Treat timestamps as first-class data and never infer them silently.
- Make every processing step report input counts, output counts, and anomalies.
- Never discard invalid data silently; record the rejected data or at least its
  count and rejection reason.
- Keep performance-critical loops simple and avoid unnecessary repeated file
  reads.
- Accompany algorithm changes with tests and validation against a known
  dataset.

## 1. Design Before Writing Code

Before implementing a component, ask Copilot to describe:

- The proposed architecture.
- The end-to-end data flow.
- Important edge cases.
- Failure modes and recovery behavior.
- Likely performance bottlenecks.
- The testing and validation strategy.

Example prompt:

> Act as a senior embedded data-engineering architect. Design a muon data
> collection and processing pipeline for a Raspberry Pi. Include acquisition,
> validation, storage, processing, visualization, and failure handling. Suggest
> the minimum viable architecture and identify the highest-risk edge cases.

## 2. Define Data Contracts Before Implementing Components

For each core component, define:

- Input schema.
- Output schema.
- Field units and valid ranges.
- Timestamp format and timezone.
- Error and rejection behavior.
- Processing assumptions.

Example prompt:

> Draft a strict data contract for raw muon log ingestion. Specify field names,
> units, timestamp format, valid ranges, and rejection rules. Include a Python
> dataclass and a validation function.

Clear contracts reduce ambiguity between acquisition, processing, storage, and
visualization code.

## 3. Create Tests Before or Alongside Implementation

For high-risk scientific code, ask Copilot to identify test cases before it
writes the implementation.

Example prompt:

> Write pytest tests for raw muon data validation, including timestamp drift,
> missing values, malformed ADC entries, duplicate records, and out-of-range
> counts. State the expected behavior for every case.

Tests should cover:

- Valid and invalid records.
- Boundary values.
- Missing, duplicate, and out-of-order records.
- Clock changes and timezone behavior.
- Truncated or partially written input files.
- Reprocessing the same data more than once.
- Known scientific results from representative datasets.

## 4. Ask for Explicit Trade-offs

Copilot should explain why a design is appropriate rather than merely produce
code.

Example prompt:

> Compare three designs for processing streaming muon data: single-threaded
> batches, a multiprocessing worker queue, and an asyncio-based reader. For a
> low-power Raspberry Pi, recommend one and explain the trade-offs in CPU use,
> memory use, reliability, complexity, and data-loss risk.

This is particularly important before introducing concurrency, caching,
databases, or new file formats.

## 5. Keep Requests Focused and Measurable

Avoid broad requests such as:

> Build the system.

Prefer requests with a clear outcome:

- Create a raw log parser that validates timestamps and emits defined records.
- Add a processing stage that aggregates counts per minute and records gaps.
- Generate daily and weekly plots with explicit units and missing-data markers.
- Add a command-line interface with configuration validation and logging.
- Benchmark throughput and peak memory against a representative input file.

A focused request is easier to review, test, and correct.

## 6. Use Copilot as a Reviewer

After implementation, ask targeted review questions:

- Review this code for race conditions, data loss, memory growth, and scientific
  correctness.
- Identify every hidden assumption in this implementation.
- Which unit, integration, and regression tests are missing?
- Which production failures could damage data integrity?
- Which Raspberry Pi deployment assumptions are fragile?
- Does the processing preserve timestamps, units, calibration, and metadata?

Review generated code before accepting it. Copilot output should be treated as
a proposed change, not as proof that the change is correct.

## 7. Require Evidence Before Declaring Success

Use a repeatable development loop:

1. Define the requirement and measurable acceptance criteria.
2. Design the component and identify failure modes.
3. Define its input and output contracts.
4. Write or update tests.
5. Implement the smallest useful change.
6. Run the relevant tests.
7. Validate the output against real or representative sample data.
8. Measure performance when performance is part of the requirement.
9. Review the change for data-integrity and deployment risks.
10. Update the relevant documentation.

Do not accept "it seems correct" as validation for scientific processing.

## Project-Specific Guardrails

The most serious risks in a muon instrumentation system include:

- Clock drift, timezone mistakes, and daylight-saving transitions.
- Silently dropped, duplicated, or reordered records.
- Unvalidated calibration values.
- Incorrect units, scaling factors, or aggregation periods.
- Log corruption, partial writes, and file truncation.
- Data loss or double counting during reprocessing.
- Hidden assumptions in plots and derived statistics.
- Fragile cron, systemd, serial-device, or mount-point assumptions.

Ask Copilot to treat these as first-class concerns in every relevant design,
implementation, and review.

## Suggested Development Phases

### Phase 1: Data Acquisition

- Document the sensor and serial data formats.
- Define the raw-data schema.
- Validate incoming records without silently losing data.
- Preserve immutable raw observations.
- Handle reconnects, partial records, file rotation, and safe shutdown.
- Record acquisition health and failures.

### Phase 2: Processing

- Aggregate data by defined periods.
- Detect and represent gaps, duplicates, and anomalies.
- Apply calibration and normalization explicitly.
- Make processing deterministic and reproducible.
- Make reprocessing idempotent where practical.
- Record software and configuration versions with derived output.

### Phase 3: Visualization

- Plot daily, weekly, and monthly trends.
- Display units and aggregation intervals clearly.
- Mark missing or invalid data rather than interpolating silently.
- Overlay anomalies and relevant environmental information.
- Ensure the displayed values can be traced to their source observations.

### Phase 4: Reliability and Operations

- Use structured and actionable logging.
- Provide failure recovery and restart behavior.
- Validate cron and systemd deployments.
- Add operational health checks.
- Monitor disk use, process health, input freshness, and clock state.
- Document installation, configuration, backup, and recovery procedures.

## Example Repository Instructions

The following rules are suitable starting points for
`.github/copilot-instructions.md`:

```markdown
# PicoMuon Project Instructions

- Treat this as a scientific data acquisition and processing project, not a
  collection of unrelated scripts.
- Prefer explicit validation and schema checking over silent coercion.
- Preserve raw data, metadata, timestamps, calibration values, and units.
- Handle missing data, malformed records, duplicates, out-of-order records, and
  outliers explicitly at every relevant processing stage.
- Use Python type hints, structured logging, clear errors, and small testable
  functions.
- Prefer streaming and bounded-memory processing for large datasets.
- Require tests and representative-data validation for algorithmic changes.
- Do not claim a change is complete without running the relevant tests and
  verifying its output.
- Avoid changing scientific behavior unless the requirement and expected result
  are documented.
- Keep Raspberry Pi resource limits and unattended operation in mind.
```

Keep always-on instructions concise. Link to detailed project documentation
instead of duplicating it.

## Practices That Minimize Mistakes

- Keep one feature or concern per focused request.
- Ask for design, tests, and edge cases before implementation.
- Review generated code before accepting it.
- Validate with real sample files in addition to synthetic test data.
- Maintain small benchmarks for throughput, latency, and memory.
- Keep raw data immutable.
- Make all derived data reproducible from raw data and versioned configuration.
- Archive the configuration and software version used for every processing run.
- Use source control and review changes in small increments.
- Separate scientific algorithm changes from unrelated refactoring.
- Record why thresholds, ranges, filters, and calibration formulas were chosen.

The goal is not to ask Copilot to make fewer decisions. The goal is to make
every important decision explicit, reviewable, testable, and reproducible.
