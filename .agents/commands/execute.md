---

description: Execute an implementation plan for an E2E ML/Data project
argument-hint: [path-to-plan]
-----------------------------

# Execute: Implement from Plan

## Plan to Execute

Read plan file: `$ARGUMENTS`

## Objective

Implement the approved plan completely and safely.

The plan defines the intended scope and implementation approach. The existing codebase and `AGENTS.md` define the project's actual conventions and constraints.

**Do not write code outside the scope of the plan unless required to fix an implementation issue or maintain project correctness.**

---

## Execution Instructions

### 1. Read and Understand

Before making changes:

* Read the ENTIRE plan
* Read `AGENTS.md`
* Understand task dependencies and execution order
* Review relevant context references
* Review the testing and validation strategy
* Identify expected files to create or modify

Check the current repository state:

!`git status`

**Do not overwrite or discard existing uncommitted user changes.**

If the working tree contains relevant uncommitted changes, account for them before modifying files.

---

### 2. Verify Plan Against Codebase

Before implementing each task:

* Read the referenced files
* Confirm the referenced patterns still exist
* Verify imports, APIs, schemas, and interfaces
* Check that planned file paths are correct

If the plan conflicts with the current codebase:

1. Prefer existing project conventions.
2. Make the smallest necessary adjustment.
3. Document the deviation in the final report.

Do not blindly follow outdated instructions.

---

### 3. Execute Tasks in Order

For EACH task in `STEP-BY-STEP TASKS`:

#### a. Understand

* Identify the target file/component
* Read relevant existing code
* Understand dependencies
* Identify potential side effects

#### b. Implement

* Follow the plan and existing project patterns
* Keep changes focused
* Reuse existing utilities and abstractions
* Avoid unnecessary refactoring
* Add appropriate type hints, documentation, and logging
* Do not introduce new dependencies unless justified by the plan

#### c. Verify

After meaningful changes:

* Check syntax/imports
* Run the task-specific validation command
* Fix issues before continuing when practical

---

### 4. ML/Data Safety Checks

When applicable, explicitly verify:

#### Data

* Data schemas remain compatible
* No unintended data mutation
* Data quality checks remain valid
* Pipeline dependencies are preserved
* Reproducibility is maintained

#### ML

* No data leakage is introduced
* Train/validation/test boundaries remain correct
* Temporal ordering is preserved where relevant
* Features use only information available at prediction time
* Evaluation methodology remains valid
* Baselines and acceptance criteria are preserved

If an implementation change invalidates the planned evaluation methodology, stop and address the issue before proceeding.

---

### 5. Implement Testing

After implementation:

* Create or update tests specified by the plan
* Follow existing project testing patterns
* Test the changed behavior
* Cover important edge cases
* Add integration/pipeline tests where required
* Add ML/data validation where applicable

Do not add arbitrary tests solely to increase coverage numbers.

---

### 6. Run Validation

Run the validation commands specified in the plan in the appropriate order.

Typical levels:

1. Syntax / formatting / linting
2. Unit tests
3. Integration tests
4. Data/pipeline validation
5. ML evaluation
6. Feature-specific or end-to-end validation

If a command fails:

* Determine whether the failure is caused by the implementation
* Fix the implementation when appropriate
* Re-run the relevant validation
* If the failure is caused by the environment, stale plan, or unrelated existing issue, document it clearly

Do not hide or ignore validation failures.

---

### 7. Final Verification

Before completing:

* Confirm all applicable tasks are implemented
* Confirm expected files were created/modified
* Confirm tests and validation were executed
* Confirm no unintended files were changed
* Review the final diff
* Confirm project conventions are followed
* Confirm documentation/configuration was updated where required

Check:

!`git diff --stat`

and, when useful:

!`git diff`

Do not commit changes unless explicitly requested.

---

# Handling Deviations

If the plan cannot be followed exactly:

### Minor Deviation

Make the smallest reasonable adjustment and continue.

### Significant Deviation

Stop and reassess when:

* The planned approach is incompatible with the existing architecture
* A data/ML assumption is invalid
* Evaluation methodology becomes unreliable
* Required dependencies are unavailable
* The requested behavior conflicts with project constraints

Document the issue and explain the chosen alternative.

Do not silently change the project's architecture or requirements.

---

# Output Report

Provide a concise report.

### Completed Tasks

* Completed tasks
* Files created
* Files modified

### Deviations

* Planned approach changed: Yes/No
* If yes, explain what changed and why

### Tests

* Tests added/modified
* Test results

### Validation

```text
<command> → PASS/FAIL
<command> → PASS/FAIL
```

For ML/data validation, include important results such as:

* Metric changes
* Baseline comparison
* Data quality results
* Pipeline validation results

### Remaining Issues

* Known failures
* Unresolved risks
* Environment limitations
* Follow-up work

### Final Status

State one:

* **READY** — implementation and required validation completed
* **READY WITH WARNINGS** — implementation completed but known non-blocking issues remain
* **BLOCKED** — implementation cannot be considered complete

Do not claim the work is ready when required validation has not been completed.

## Notes

* Do not commit changes unless explicitly requested.
* Do not discard existing user changes.
* Do not modify source datasets or generated artifacts unless the plan explicitly requires it.
* Do not skip validation silently.
* Keep implementation changes focused on the plan.
* If the plan is incorrect, adapt carefully and document the deviation.
