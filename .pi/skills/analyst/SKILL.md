---
name: analyst
description: Rules for data analysis, plots, and statistics. Use when analyzing data, making plots, or running statistics.
---

# Analyst Mode

Follow these rules to analyze data, generate plots, and work with the user.

---

## Stage 1: Discovery and Plan

1. **Inspect Data**:
   - Search files in `data/`.
   - Read schemas, sample counts, variables, and metadata.
   - If the request is general, summarize available data and propose high-level options.

2. **Propose Plan**:
   - Provide a brief plan with three elements:
     - **Inputs**: Datasets and metadata to use.
     - **Outputs**: Types of analyses and plots to create (e.g., summary table, volcano plot).
     - **Approach**: High-level strategy (e.g., compare group A with group B).
   - Keep descriptions brief. Do not include implementation details or specific code functions.

---

## GATE 1: Plan Approval (HARD STOP)

- **DO NOT** write or execute analysis code before plan approval.
- Wait for explicit user approval ("Go") before you start Stage 2.

---

## Stage 2: Incremental Execution

1. **Execute Step**:
   - Run code for the approved initial step only.
   - Inspect generated files and plots to verify correctness.

2. **Present Results**:
   - Present primary outputs (e.g., summary tables, plots, key statistics) directly as live cells/visualizations in the user's active notebook workspace.
   - **DO NOT** execute unrequested follow-up analyses or secondary plots in the same turn.

---

## GATE 2: Iterative Review (HARD STOP)

- Stop after you present the primary results.
- Wait for user feedback and instructions before you perform the next analysis step.

---

## Stage 3: Verification and Lock-Down

1. **Verify Reproducibility**:
   - Run the complete analysis code end-to-end.
   - Confirm that all outputs generate without errors.

2. **Summarize Deliverables**:
   - Present final findings and list completed deliverables.

---

## GATE 3: Final Approval

- Wait for final user confirmation that the analysis meets requirements.
