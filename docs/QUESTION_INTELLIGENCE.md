# Question Intelligence & Architecture Update

This document introduces a "Question Intelligence" layer and expanded architecture to turn the existing multi-agent pipeline into an AI data analyst capable of understanding user questions, planning analysis, running multi-agent computations, and producing human-ready insights.

## 1. The Problem With Most Agent Pipelines

Typical pipelines are: Dataset → Agents → Insights

But real analytics starts with a question. Examples:
- Why did revenue drop in Q3?
- Which customer segment buys the most?
- What factors influence churn?

Systems must first understand intent, then decide what analysis to run.

## 2. The Missing Component: Question Understanding

Add a Query Intelligence Layer that sits before the analysis planner:

User Question
      │
      ▼
Question Understanding Agent
      │
      ▼
Analysis Planner
      │
      ▼
Agent Pipeline

This converts the tool into an AI data analyst that knows what the user wants and runs deterministic analyses.

## 3. Full Architecture (Production-Level)

                        ┌─────────────────────┐
                        │ User Interface      │
                        │ (Upload + Question) │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │ Question Interpreter│
                        │ Understand intent   │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │ Analysis Planner    │
                        │ Decide analysis     │
                        └──────────┬──────────┘
                                   │
                                   ▼
                ┌───────────────────────────────────┐
                │ Multi-Agent Analysis Pipeline     │
                │ 1. Data Janitor                   │
                │ 2. Hypothesis Bot                 │
                │ 3. Experiment Agent               │
                │ 4. Debate Manager                 │
                │ 5. Viz Whiz                       │
                └───────────────┬───────────────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ Insight Generator   │
                     │ Narrative summary   │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ Results Dashboard   │
                     │ Charts + Insights   │
                     └─────────────────────┘

## 4. What Each Layer Does

1) Question Interpreter

Purpose: parse user intent into a structured query so analysis is focused and deterministic.

Example input:

Which region has the highest sales?

Example output:

{
  "intent": "comparison",
  "metric": "sales",
  "dimension": "region"
}

2) Analysis Planner

Purpose: given the interpreted question and dataset schema, produce an ordered analysis plan.

Example plan:
1. Clean dataset
2. Aggregate sales by region
3. Rank regions
4. Generate bar chart

3) Multi-Agent Analysis Pipeline

This is the existing pipeline (Data Janitor, Hypothesis Bot, Experiment Agent, Debate Manager, Viz Whiz) that executes the planner's steps.

4) Insight Generator

LLMs produce human-readable explanations from numeric results.

Example output:

Sales are highest in Nairobi, accounting for 38% of total revenue.

The strongest predictor of high purchase frequency is customer income (r=0.62).

## 5. Data Infrastructure Layer

Production systems need artifact storage and state management. Suggested components:

- FastAPI backend
- PostgreSQL → metadata & insights
- Redis → agent state / cache
- Object storage (S3-compatible) → charts & datasets

## 6. Example Real Workflow

User uploads `sales_data.csv` and asks "Why did revenue drop last quarter?"

System executes:
Question Interpreter → detects `trend analysis`
Planner →
1. Group revenue by quarter
2. Detect change points and trend shifts
3. Identify influencing variables (region, customer_type)

Agents run the analysis and output:
- Revenue dropped 12% in Q3.
- Primary factors: Reduced purchases in Western region; Lower repeat purchases from enterprise customers.
Plus charts and explanations.

## 7. What Makes This Powerful

Combining LLM reasoning, data science computation, and multi-agent orchestration produces a deterministic, explainable AI analyst.

## 8. Why This Is a Strong Portfolio Project

- Demonstrates system architecture and orchestration
- Shows integration of LLMs with analytics
- Relevant to AI engineering and data platform roles

## 9. Advanced Feature: Continuous Learning (Optional)

Store past analyses, successful hypotheses, and dataset patterns to improve planner decisions and hypothesis prioritization over time.

## Next Steps (Phase 2 plan)

1. Run tests on the existing agent pipeline (Phase 2 testing).
2. Integrate a lightweight Question Interpreter prototype.
3. Implement a simple Analysis Planner that maps intents → agent sequences.
4. Evaluate results and iterate; then expand infra (Postgres/Redis/Object storage) as needed.

---

References:
- See existing agents documentation in [AGENTS.md](AGENTS.md)
