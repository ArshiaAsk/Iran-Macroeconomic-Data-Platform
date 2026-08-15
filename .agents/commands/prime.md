---

## description: Prime agent with E2E ML/Data project understanding

# Prime: Load Project Context

## Objective

Build a practical understanding of the project before making changes.

Analyze the repository structure, documentation, data/ML workflow, configuration, and key implementation files. The goal is to understand **what the project does, how it works, its current state, and the rules an agent must follow**.

Do not modify any files.

---

## Process

### 1. Analyze Project Structure

List tracked files:

!`git ls-files`

Show the relevant directory structure:

!`tree -L 3 -I 'node_modules|__pycache__|.git|dist|build|.venv|venv'`

Identify:

* Source code
* Data/pipeline directories
* Notebooks
* Tests
* Configuration
* Models/artifacts
* Deployment/infrastructure
* Documentation

Do not read generated data, model artifacts, or large files unless necessary.

---

### 2. Read Core Documentation

Read, when available:

* `PRD.md` or equivalent requirements document
* `AGENTS.md` or equivalent global rules
* Root `README.md`
* Relevant README files in major directories
* Architecture/design documentation
* Data documentation
* ML/research documentation
* Planning documents relevant to the current project state

Treat these documents as the primary source of project intent and conventions.

---

### 3. Identify Key Files

Based on the project structure, identify and inspect the most important files.

Include where applicable:

* Entry points
* `pyproject.toml`, `requirements.txt`, or equivalent
* Configuration files
* Data ingestion/processing pipelines
* Data schemas
* Feature definitions
* Training code
* Evaluation code
* Inference/serving code
* Database schemas/models
* API definitions
* Tests
* Deployment/orchestration configuration

Prioritize files that explain the **actual execution flow** rather than reading everything.

---

### 4. Understand the E2E Workflow

Determine the project's actual lifecycle.

For ML/Data projects, identify the applicable flow:

```text
Data Sources
    ↓
Ingestion
    ↓
Validation
    ↓
Transformation / Features
    ↓
Training / Analysis
    ↓
Evaluation
    ↓
Inference / Output
    ↓
Deployment
    ↓
Monitoring
```

Only include stages that actually exist.

Identify:

* Where data enters the system
* How it is transformed
* Where models/analysis are created
* How evaluation is performed
* How outputs are consumed
* How the system is deployed or executed
* How failures are detected

---

### 5. Understand Validation & Quality

Identify the project's existing validation approach.

For ML projects, inspect:

* Train/validation/test strategy
* Cross-validation
* Temporal validation
* Baselines
* Evaluation metrics
* Leakage prevention
* Reproducibility
* Model comparison

For Data projects, inspect:

* Data quality checks
* Schema validation
* Pipeline validation
* Freshness/completeness checks

Do not assume a best practice is implemented if the codebase does not show it.

---

### 6. Check Current State

Check recent activity:

!`git log -10 --oneline`

Check current branch and working tree:

!`git status`

Identify:

* Current branch
* Recent development focus
* Uncommitted changes
* Obvious incomplete work
* Important recent changes

Do not modify or clean the working tree.

---

## Output Report

Provide a concise, scannable summary.

### Project Overview

* Purpose
* Project type
* Current state
* Primary workflow

### Tech Stack

* Languages
* Frameworks/libraries
* Data/ML tools
* Databases/storage
* Infrastructure/deployment tools

### Project Structure

* Important directories
* Responsibilities of major components

### E2E Workflow

Summarize the actual:

`Data → Processing → ML/Analytics → Evaluation → Deployment/Output`

workflow where applicable.

### Core Principles

Identify observed:

* Coding conventions
* Data conventions
* ML/evaluation conventions
* Testing approach
* Reproducibility requirements
* Important project rules

### Current State

* Active branch
* Recent changes
* Current development focus
* Important incomplete work

### Important Observations

Highlight only meaningful findings such as:

* Potential risks
* Missing documentation
* Unclear architecture
* Data/ML concerns
* Inconsistencies
* Important dependencies

Do not turn observations into unsolicited implementation tasks.

---

## Rules

* Do not modify files.
* Do not invent project requirements or conventions.
* Prefer project documentation and actual code over assumptions.
* Do not read the entire repository indiscriminately.
* Prioritize files that explain the project's behavior and workflow.
* Distinguish between **documented intent** and **observed implementation**.
* If they conflict, explicitly mention the discrepancy.
* Do not criticize existing decisions unless they create an obvious inconsistency or risk.
* Keep the final report concise enough to use as working context for the next task.
