---

## description: "Create an implementation plan for an E2E ML/Data task with focused codebase analysis"

# Plan a New Task

## Task: $ARGUMENTS

## Mission

Transform a task or feature request into a **clear, implementation-ready plan** through focused codebase analysis and research.

**Core Principle:** Do NOT write code in this phase.

The plan should provide the implementation agent with the context needed to make the change correctly: relevant files, existing patterns, dependencies, data/ML considerations, implementation steps, and validation.

Avoid unnecessary analysis or architecture changes unrelated to the task.

---

## Planning Process

### Phase 1: Task Understanding

Determine:

* What problem is being solved?
* Why is the change needed?
* What type of change is this?

  * New Capability
  * Enhancement
  * Refactor
  * Bug Fix
  * Data Pipeline Change
  * ML/Experiment Change
* What systems, datasets, pipelines, models, or interfaces are affected?
* What is explicitly out of scope?

When useful, define:

```text
As a <user/stakeholder/system>
I want to <action/goal>
So that <benefit/value>
```

---

### Phase 2: Codebase & Data/ML Analysis

Analyze the existing project before designing the change.

#### 1. Project Structure

Identify:

* Relevant directories and modules
* Entry points
* Configuration
* Data pipelines
* Training/evaluation code
* APIs/services
* Tests
* Deployment/infrastructure

#### 2. Existing Patterns

Find similar implementations and document:

* Naming conventions
* File/module organization
* Error handling
* Logging
* Configuration
* Testing patterns
* Data processing patterns
* ML/evaluation patterns

Check `AGENTS.md` for project-specific rules.

#### 3. Dependencies

Identify relevant:

* Existing libraries
* Internal modules
* External services
* Data sources
* APIs

Prefer existing dependencies and patterns when they already solve the problem.

Research external documentation only when needed.

#### 4. Data / ML Impact

When applicable, determine:

* Which datasets are affected
* Data schema changes
* Pipeline dependencies
* Feature changes
* Training/inference impact
* Evaluation impact
* Model/versioning implications
* Leakage risks
* Temporal validation requirements
* Reproducibility requirements

#### 5. Testing & Validation

Identify the project's existing:

* Unit tests
* Integration tests
* Data validation
* Model evaluation
* Pipeline validation
* Linting/type checking
* End-to-end validation

Use the project's existing standards rather than inventing new ones.

---

### Phase 3: Research

Research external documentation only when the task depends on:

* A library/API that needs verification
* Version-specific behavior
* A new technology
* A known compatibility issue
* An implementation detail not sufficiently documented in the repository

Prefer official documentation.

Record only research that directly affects implementation.

---

### Phase 4: Design & Risk Analysis

Determine:

* How the change fits the existing architecture
* Which existing patterns should be reused
* Dependencies and implementation order
* Edge cases and failure modes
* Backward compatibility requirements
* Data/ML risks
* Performance implications
* Security considerations where relevant

Choose between alternatives only when a real design decision exists.

Avoid introducing unnecessary architecture or infrastructure.

---

# Plan Structure

Create:

`.agents/plans/{kebab-case-descriptive-name}.md`

Use the following structure:

````markdown
# Task: <task-name>

## Task Description

<Detailed description of the requested change and why it is needed>

## Scope

### In Scope
- [ ] <item>

### Out of Scope
- [ ] <item>

## Context

<Relevant project context and current behavior>

## Proposed Approach

<Concise explanation of how the change should be implemented>

## Task Metadata

**Type:** [New Capability/Enhancement/Refactor/Bug Fix/Data/ML]
**Complexity:** [Low/Medium/High]
**Affected Areas:** <components>
**Dependencies:** <dependencies>

---

## CONTEXT REFERENCES

### Files to Read Before Implementation

- `path/to/file.py` - <why it matters>
- `path/to/test.py` - <pattern to follow>
- `path/to/config.py` - <relevant configuration>

### Data / ML References

- `path/to/pipeline.py` - <relevant data flow>
- `path/to/train.py` - <training pattern>
- `path/to/evaluate.py` - <evaluation pattern>

### External Documentation

- <official documentation URL> - <specific section and why>

### Patterns to Follow

**Naming:** <project pattern>

**Structure:** <project pattern>

**Testing:** <project pattern>

**Data/ML:** <relevant project pattern>

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation

<Required preparation, configuration, schemas, dependencies, or data changes>

### Phase 2: Core Change

<Main implementation>

### Phase 3: Integration

<Integration with existing pipelines, APIs, models, or components>

### Phase 4: Validation

<Tests, evaluation, data checks, and final validation>

---

## STEP-BY-STEP TASKS

Execute tasks in dependency order.

### {ACTION} {target}

- **IMPLEMENT:** <specific change>
- **PATTERN:** <existing file:line to follow>
- **DEPENDENCIES:** <required dependencies>
- **GOTCHA:** <important constraint>
- **VALIDATE:** `<executable command>`

Use actions such as:

- CREATE
- UPDATE
- ADD
- REMOVE
- REFACTOR
- MIRROR

---

## TESTING & VALIDATION

### Unit Tests

<Tests required for changed logic>

### Integration Tests

<Tests required for component/pipeline integration>

### Data Validation

<Relevant schema, quality, freshness, or pipeline checks>

### ML Validation

When applicable:

- Baseline comparison
- Evaluation metrics
- Appropriate validation strategy
- Leakage checks
- Temporal/out-of-sample validation
- Reproducibility checks

### Edge Cases

<List important cases>

---

## VALIDATION COMMANDS

### Level 1: Static / Style

```bash
<project-specific commands>
````

### Level 2: Unit Tests

```bash
<project-specific commands>
```

### Level 3: Integration / Pipeline Tests

```bash
<project-specific commands>
```

### Level 4: Feature-Specific Validation

```bash
<project-specific commands>
```

### Level 5: Manual Validation

<Only when required>

---

## ACCEPTANCE CRITERIA

* [ ] Requested behavior is implemented
* [ ] Existing project patterns are followed
* [ ] Relevant tests pass
* [ ] Data validation passes where applicable
* [ ] ML evaluation passes defined criteria where applicable
* [ ] No data leakage or invalid evaluation methodology introduced
* [ ] No regressions in existing functionality
* [ ] Documentation/configuration updated where necessary

---

## RISKS & TRADE-OFFS

* <Risk and mitigation>
* <Important assumption>
* <Known limitation>

## NOTES

<Important implementation details, decisions, or unresolved questions>

```

---

## Quality Criteria

### Context Completeness

- [ ] Relevant files identified
- [ ] Existing patterns documented
- [ ] Data/ML dependencies identified
- [ ] External documentation included only when necessary
- [ ] Important risks and constraints captured

### Implementation Readiness

- [ ] Tasks are ordered by dependency
- [ ] Tasks are specific and actionable
- [ ] Each important task has a validation method
- [ ] File references are concrete
- [ ] No unnecessary implementation work is included

### ML/Data Correctness

When applicable:

- [ ] Data dependencies are understood
- [ ] Evaluation methodology is appropriate
- [ ] Leakage risks are considered
- [ ] Temporal ordering is respected
- [ ] Baselines are considered
- [ ] Reproducibility is considered

### Scope Control

- [ ] MVP/task scope is clear
- [ ] Unrelated refactoring is excluded
- [ ] New dependencies are justified
- [ ] Architecture changes are justified

---

## Output

After creating the plan, report:

- Summary of the proposed approach
- Full path to the plan
- Complexity assessment
- Key risks or decisions
- Any unresolved questions
- Confidence in the implementation plan: `#/10`
```

The confidence score should reflect **how well the repository and requirements are understood**, not a guarantee that implementation will succeed in one pass.
