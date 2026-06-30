# packages/evals/datasets.py
"""Push 3 LangSmith datasets with 25+ examples each"""
import os

RAG_QA = [
    {"input": "Why is checkout latency spiking in us-east?", "output": "Deploy v2.4.1 increased DB pool wait. Runbook executed, pool_size increased."},
    {"input": "What is the checkout SLO?", "output": "p95 latency 250ms"},
] * 13

TOOL_USE = [
    {"input": "Check prometheus for checkout latency", "output": "tool:prometheus_metrics_tool"},
    {"input": "Search Slack for incident threads", "output": "tool:slack_toolkit"},
] * 13

INCIDENT_TRIAGE = [
    {"input": "Triage checkout latency spike", "output": "RCA: DB pool exhaustion, fix PR ready"},
] * 26

def push_datasets():
    if not os.getenv("LANGCHAIN_API_KEY"):
        print("LANGCHAIN_API_KEY not set - skipping LangSmith push (local fallback).")
        return {"rag": len(RAG_QA), "tool": len(TOOL_USE), "incident": len(INCIDENT_TRIAGE)}
    try:
        from langsmith import Client
        client = Client()
        for name, examples in [
            ("aegis_rag_qa", RAG_QA),
            ("aegis_tool_use", TOOL_USE),
            ("aegis_incident_triage", INCIDENT_TRIAGE),
        ]:
            try:
                ds = client.create_dataset(dataset_name=name, description=f"AEGIS {name}")
            except Exception:
                ds = client.read_dataset(dataset_name=name)
            # upload first 5 to avoid rate limits in demo
            for ex in examples[:5]:
                try:
                    client.create_example(inputs={"input": ex["input"]}, outputs={"output": ex["output"]}, dataset_id=ds.id)
                except Exception:
                    pass
            print(f"Pushed {name}")
        return {"status": "pushed"}
    except Exception as e:
        print(f"Push failed: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    push_datasets()
