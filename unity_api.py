#!/usr/bin/env python3
import os
from typing import Optional
from fastapi import FastAPI
import uvicorn

from warehouse import Warehouse

app = FastAPI()
_model: Optional[Warehouse] = None
_config_path = os.environ.get("WAREHOUSE_CONFIG", "layout.json")
# Coordination modes (see README): auction + blackboard by default for the demo
_allocation_mode = os.environ.get("WAREHOUSE_ALLOCATION", "auction")
_conflict_mode = os.environ.get("WAREHOUSE_CONFLICT", "blackboard")

@app.post("/start")
def start(allocation: Optional[str] = None, conflict: Optional[str] = None):
    global _model
    _model = Warehouse(parameters={
        "config_path": _config_path,
        "allocation_mode": allocation or _allocation_mode,
        "conflict_mode": conflict or _conflict_mode,
    })
    _model.setup()
    # Good defaults for a demo loop
    try:
        _model.auto_cycle_reset = True
        _model.epsilon_override = 0.05
    except Exception:
        pass
    return {"ok": True, "allocation_mode": _model.allocation_mode, "conflict_mode": _model.conflict_mode}

@app.post("/step")
def step(steps: int = 1):
    if _model is None:
        start()
    for _ in range(max(1, int(steps))):
        _model.step()
    return _model.serialize_for_unity()

@app.get("/state")
def state():
    if _model is None:
        start()
    return _model.serialize_for_unity()

@app.get("/blackboard")
def blackboard():
    """Full blackboard snapshot: tasks with bids, reservations, congestion, events."""
    if _model is None:
        start()
    return {
        "allocation_mode": _model.allocation_mode,
        "conflict_mode": _model.conflict_mode,
        "blackboard": _model.blackboard.snapshot(max_events=50),
    }

if __name__ == "__main__":
    uvicorn.run("unity_api:app", host="127.0.0.1", port=8000, reload=False)
