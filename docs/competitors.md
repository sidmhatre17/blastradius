# Competitors (honest notes)

BlastRadius does **not** claim to invent blast-radius analysis. Related products / ideas include:

| Name | Rough focus | How BlastRadius relates |
|------|-------------|-------------------------|
| **Arbor** | Deeper code-impact / call-graph style analysis | Arbor is stronger on graph sophistication. BlastRadius is an open MVP with **incident retrieval + explainable score**, not a call-graph competitor. |
| **CodeDig** | Change understanding / dig into impact | Overlaps on “what does this change touch?” Narrative here emphasizes **incident heat** and portfolio-demo clarity. |
| **CodeRadius** | Blast-radius naming / impact framing | Same category family. Differentiation is implementation transparency + deterministic factors you can audit in the report JSON. |

## What we deliberately do not claim

- “World’s first blast-radius tool”
- Production parity with commercial impact engines
- Perfect static analysis

## What we do claim (for this repo)

- End-to-end system you can clone and run at **$0** (local embeddings + optional Ollama)
- Deterministic risk score with six named factors
- Incident-memory retrieval with overlap boost (works even under CI hash embeddings)
- Curated PayOrbit demo with expected tier/incident gates

## Interview framing

Lead with: *change impact graph + incident memory + explainable score*.  
When asked about Arbor: acknowledge call-graph depth; explain MVP import heuristics and how you’d evolve the graph without changing the scoring contract.
