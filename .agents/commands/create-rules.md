---

## description: Analyze an E2E ML/Data project and create global AGENTS.md rules

# Create Global Rules

## Overview

Analyze the project and create an `AGENTS.md` file containing the project-specific rules, conventions, workflows, and technical context that an AI coding agent should follow.

This command is designed for **E2E Machine Learning, Data Engineering, Analytics, and ML/Data Production projects**.

The goal is not to document the entire codebase. Extract only the information that an agent needs to work correctly and consistently in the project.

---

## Objective

Create project-specific global rules covering:

* What the project does
* Project type and lifecycle
* Technologies and tools
* Repository structure
* Data and ML workflow
* Coding and naming conventions
* Testing and validation
* Important constraints
* Key files and documentation

---

# Phase 1: DISCOVER

## Identify Project Type

Determine the primary project type:

| Type          | Indicators                                   |
| ------------- | -------------------------------------------- |
| Data Pipeline | ETL/ELT, ingestion, transformation workflows |
| ML Project    | Training, evaluation, experimentation        |
| ML Production | Training + serving + monitoring              |
| Data Platform | Data storage, pipelines, analytical layers   |
| Analytics     | Metrics, analysis, reporting                 |
| Forecasting   | Time-series data and forecasting workflow    |
| Research      | Experiments, notebooks, scientific analysis  |
| Hybrid        | Combination of the above                     |

A project may have multiple characteristics.

## Analyze Configuration

Inspect relevant configuration files such as:

```text
pyproject.toml
requirements.txt
environment.yml
Dockerfile
docker-compose.yml
Makefile
.pre-commit-config.yaml
configs/
```

Also inspect ML/data-specific configuration where present.

## Map Directory Structure

Understand:

* Source code
* Tests
* Notebooks
* Data-related directories
* Configuration
* Pipelines
* Models
* Scripts
* Documentation
* Deployment/infrastructure

---

# Phase 2: ANALYZE

## Extract Tech Stack

Identify relevant:

* Language/runtime
* Data processing frameworks
* ML frameworks
* Databases/storage
* APIs
* Testing tools
* Experiment/tracking tools
* Deployment tools
* Orchestration tools
* Linting/formatting

Only include technologies actually found in the project.

## Identify Data/ML Patterns

Study existing implementation for:

* Data ingestion patterns
* Transformation conventions
* Feature engineering
* Train/validation/test strategy
* Time-series validation
* Model training
* Evaluation
* Model persistence
* Inference
* Configuration
* Reproducibility

Pay particular attention to project-specific rules around:

* Data leakage
* Temporal ordering
* Random seeds
* Feature availability
* Experiment reproducibility

Only document patterns that actually exist or are clearly established project rules.

## Identify Code Patterns

Study:

* Naming conventions
* Module organization
* Error handling
* Type hints
* Logging
* Configuration
* Testing patterns

## Find Key Files

Identify important:

* Entry points
* Configuration files
* Pipeline definitions
* Training scripts
* Evaluation scripts
* Core modules
* Notebooks
* Dataset definitions
* Deployment files
* Documentation

---

# Phase 3: GENERATE

## Create AGENTS.md

Use the template at:

`.agents/AGENTS-template.md`

as the starting point.

**Output path:** `AGENTS.md` in the project root.

Adapt the template to the actual project:

* Remove irrelevant sections
* Add project-specific sections when necessary
* Keep the file concise
* Prefer rules and patterns over explanations
* Do not duplicate detailed documentation

### Key Sections

1. **Project Overview**
2. **Project Type & Workflow**
3. **Tech Stack**
4. **Commands**
5. **Project Structure**
6. **Data/ML Workflow**
7. **Code Patterns**
8. **Testing & Validation**
9. **Key Files**
10. **Important Constraints**

Optional:

* Architecture
* Data conventions
* ML evaluation rules
* Deployment
* Monitoring
* On-demand context references

---

# Phase 4: OUTPUT

After creating the file, report:

```markdown
## Global Rules Created

**File:** `AGENTS.md`

### Project Type
{Detected project type}

### Tech Stack
{Key technologies}

### Data/ML Workflow
{Brief workflow summary}

### Structure
{Brief structure overview}

### Next Steps
1. Review `AGENTS.md`
2. Add project-specific rules if needed
3. Remove anything inaccurate or unnecessary
4. Add detailed reference documents only when useful
```

---

## Rules

* Keep `AGENTS.md` focused and scannable.
* Do not document every file in the repository.
* Do not invent technologies or workflows.
* Do not turn project conventions into generic best practices.
* Prefer observed project patterns over assumptions.
* Treat data and ML workflow as first-class context when applicable.
* Do not prescribe architecture unless it already exists.
* Do not duplicate information that belongs in dedicated documentation.
* Update the rules when important project conventions change.
