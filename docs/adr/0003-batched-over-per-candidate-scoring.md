# 3. Batched over Per-Candidate Scoring

Date: 2026-07-25

## Status
Accepted

## Context
When extracting short clips from a long-form podcast transcript, we may identify dozens of potential candidate moments. To determine which clips are the strongest to publish, the LLM must score them.
We could prompt the LLM independently for each candidate clip (Per-Candidate Scoring).

## Decision
We will use **Batched Scoring**. All candidate clips from a single source video will be compiled into a single prompt, asking the LLM to review them as a cohort and select the top X clips, ranking them relative to each other.

## Consequences
- **Positive:** Massive reduction in total inference time and token consumption, which is critical when running locally on limited hardware. The LLM also has the context of the entire candidate pool, allowing it to naturally select the best relative options rather than assigning arbitrary high scores to mediocre clips in isolation.
- **Negative:** Context windows must be large enough to hold all candidates in a single prompt. If a video generates 100+ candidates, we may hit context length limits and have to implement chunked batching.
