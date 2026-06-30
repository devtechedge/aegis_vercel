# packages/evals/evaluators.py
def faithfulness(outputs: dict, reference_outputs: dict) -> dict:
    # LLM-as-judge mock
    return {"key": "faithfulness", "score": 0.87}

def correctness(outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "correctness", "score": 0.84}

def tool_trajectory_accuracy(outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "tool_trajectory_accuracy", "score": 0.91}

def latency_p95(outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "latency_p95_ms", "score": 820}

def cost_usd(outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "cost_usd", "score": 0.012}
