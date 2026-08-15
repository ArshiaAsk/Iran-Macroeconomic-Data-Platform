---

description: Create a Product Requirements Document for an E2E ML/Data project from conversation
argument-hint: [output-filename]
--------------------------------

# Create PRD: Generate Product Requirements Document

## Overview

Generate a concise, professional Product Requirements Document (PRD) based on the current conversation, requirements, constraints, and goals.

This command is designed for **E2E Machine Learning, Data Engineering, Analytics, and Data/ML production projects**.

The PRD should define **what problem we are solving, why it matters, what the MVP must accomplish, and how success will be measured** without prematurely designing the entire system.

## Output File

Write the PRD to: `$ARGUMENTS` (default: `PRD.md`)

## PRD Structure

Create a well-structured PRD with the following sections. Adapt depth based on the project.

### 1. Executive Summary

* Problem being solved
* Proposed solution at a high level
* Core value proposition
* MVP goal

### 2. Problem & Objectives

* Problem statement
* Business/user impact
* Primary objectives
* Non-objectives / explicit boundaries

### 3. Target Users & Use Cases

* Primary users/stakeholders
* Their needs and pain points
* 3-6 core use cases
* Decisions or actions supported by the system

### 4. MVP Scope

* **In Scope:** Core capabilities for MVP using `- [ ]`
* **Out of Scope:** Deferred capabilities using `- [ ]`
* Group when useful:

  * Product
  * Data
  * ML/Analytics
  * Infrastructure
  * Deployment

### 5. Data Requirements

* Required data sources
* Important entities/features
* Data granularity and frequency
* Historical coverage
* Data quality requirements
* Known data limitations or dependencies

### 6. ML / Analytics Requirements

Include when applicable.

* Problem formulation
* Target/output definition
* Prediction/analysis horizon
* Baseline approach
* Evaluation metrics
* Validation strategy
* Acceptance thresholds
* Leakage or information-availability constraints

For time-series projects, explicitly consider chronological splits, walk-forward validation, and temporal holdouts.

Do not prescribe a specific model or algorithm unless it is an established requirement.

### 7. Solution Context

* High-level system responsibilities
* Existing systems or components
* Major integrations
* Important technical/business constraints
* High-level architecture considerations only

Do not turn the PRD into a detailed architecture document.

### 8. Technology & Infrastructure

* Required technologies only when already decided or constrained
* Relevant databases/storage
* APIs/integrations
* Deployment environment
* Important infrastructure constraints

Avoid choosing technologies merely because they are common.

### 9. Non-Functional Requirements

* Reliability
* Performance/latency
* Scalability
* Reproducibility
* Security/privacy
* Maintainability

Include only requirements relevant to the project.

### 10. Monitoring & Operations

Include when applicable.

* Data quality/freshness monitoring
* Pipeline/job monitoring
* Model performance/drift monitoring
* System health
* Alerting requirements

### 11. Success Criteria

* MVP success definition
* Functional acceptance criteria using `- [ ]`
* Data quality criteria
* ML/analytics criteria
* Business/user outcome criteria
* Production-readiness criteria when applicable

Success criteria must be measurable whenever possible.

### 12. Risks, Assumptions & Unknowns

* 3-5 major risks and mitigations
* Important assumptions
* Unresolved questions
* Research uncertainties that must be validated

Clearly distinguish **known requirements** from **hypotheses that still need validation**.

### 13. Implementation Phases

Break the project into 3-5 high-level phases.

Each phase should include:

* Goal
* Key deliverables using `- [ ]`
* Validation / exit criteria

Prefer phases such as:

1. Problem & Data Validation
2. MVP / Baseline
3. ML/Analytics Validation
4. Productionization
5. Monitoring & Iteration

Adapt these to the actual project.

### 14. Future Considerations

* Post-MVP improvements
* Additional data sources
* Advanced models/features
* Scaling opportunities
* Additional integrations

Keep these separate from MVP scope.

### 15. Appendix

Include only when useful:

* Related documents
* Repository structure
* Glossary
* Important references
* Existing system information

## Instructions

### 1. Extract Requirements

* Review the available conversation context
* Identify explicit requirements and implicit needs
* Capture business goals, technical constraints, data constraints, and success criteria
* Do not invent requirements simply to fill the template

### 2. Keep the MVP Realistic

* Define the smallest useful version of the system
* Aggressively separate MVP from future work
* Do not introduce unnecessary infrastructure or complexity
* Do not assume every project requires ML

### 3. ML/Data Specific Rules

When ML is involved:

* Define the problem before the model
* Establish a meaningful baseline
* Define evaluation before model comparison
* Consider data leakage
* Respect information available at prediction time
* Use validation appropriate to the data-generating process
* Prefer out-of-sample evidence over training performance

When data is central:

* Treat data availability as a project dependency
* Document important quality and freshness requirements
* Identify known data limitations
* Consider reproducibility and lineage where relevant

### 4. Avoid Premature Architecture

The PRD describes **what the system needs to achieve**, not every implementation detail.

Do not automatically introduce:

* Microservices
* Kubernetes
* Feature stores
* Streaming
* Complex orchestration
* Multiple databases
* Automated retraining

unless the requirements justify them.

### 5. Write the PRD

* Use clear, professional language
* Prefer concrete requirements over vague descriptions
* Use Markdown headings, lists, tables, and checkboxes
* Keep the document comprehensive but concise
* Maintain consistent terminology
* Clearly label assumptions and unknowns

## Quality Checks

Before finalizing:

* [ ] Problem and value proposition are clear
* [ ] MVP boundary is realistic
* [ ] In-scope and out-of-scope items are explicit
* [ ] Data requirements are defined when applicable
* [ ] ML problem and baseline are defined when applicable
* [ ] Evaluation methodology is appropriate
* [ ] Leakage/information availability is considered
* [ ] Success criteria are measurable
* [ ] Risks, assumptions, and unknowns are separated
* [ ] Implementation phases are actionable
* [ ] No unnecessary technologies or architecture were introduced

## Output Confirmation

After creating the PRD:

1. Confirm the file path.
2. Give a brief summary of the PRD.
3. Highlight important assumptions or unknowns.
4. Suggest the next appropriate planning step.

## If critical information is genuinely missing and prevents a meaningful PRD, ask focused clarification questions instead of inventing requirements.

## Notes

This command creates the **requirements layer** of an E2E ML/Data project.

It should provide enough context for subsequent architecture, data/ML design, implementation, and validation commands without duplicating those documents.
