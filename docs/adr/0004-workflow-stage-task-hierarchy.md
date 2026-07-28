# 4. Workflow, Stage, and Task Hierarchy over Flat Job Queue

Date: 2026-07-28

## Status
Accepted

## Context
Initially, the system used a flat `Job` model to track work (e.g., a "process video" job). As the transcription loop and topic extraction processes were designed for Phase 1, it became clear that failing at a late stage (like topic extraction) would require re-running the entire job (including the expensive download and transcribe steps) if we didn't have granular state tracking.

## Decision
We refactored the execution engine from a flat `Job` queue to a hierarchical `Workflow` -> `WorkflowStage` -> `Task` model. 
- **Workflow**: The overall parent process (e.g., "Process Podcast #391").
- **WorkflowStage**: A logical grouping of work (e.g., "Download", "Transcribe").
- **Task**: The atomic unit of work executed by a `Worker` (e.g., "Download Audio", "Extract Topics").

## Consequences
- **Positive**: We achieve idempotent restarts. If a `Task` fails (e.g., the LLM crashes during topic extraction), we can retry just that `Task` without re-running the earlier `Tasks` in previous `Stages`.
- **Negative**: The database schema and query logic are slightly more complex, requiring state roll-ups (a Stage is complete when all its Tasks are complete; a Workflow is complete when all its Stages are complete).
