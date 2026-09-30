"""Tests for the Blackboard, the task auction and their integration in Warehouse."""
import contextlib
import io
import os
import random
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from blackboard import Blackboard, OPEN, CLAIMED, PICKED, DONE  # noqa: E402
from auction import Auctioneer, INF  # noqa: E402


# ------------------------------------------------------------ blackboard
def test_occupant_stays_and_merge():
    bb = Blackboard()
    # robot 1 stays at (1,1); robot 2 wants to enter (1,1); robots 3 and 4 merge on (5,5)
    proposals = {1: ((1, 1), (1, 1)), 2: ((1, 2), (1, 1)),
                 3: ((4, 5), (5, 5)), 4: ((6, 5), (5, 5))}
    granted = bb.resolve_moves(proposals, priority={1: 0, 2: 10, 3: 5, 4: 1})
    assert granted[1] == (1, 1)
    assert granted[2] == (1, 2)          # occupant stays, even vs higher priority
    assert granted[3] == (5, 5)          # higher priority wins the merge
    assert granted[4] == (6, 5)          # loser waits
    assert len(set(granted.values())) == 4
    assert bb.congestion_at((5, 5)) > 0


def test_head_on_swap_is_blocked_and_side_step_used():
    bb = Blackboard()
    proposals = {1: ((2, 2), (3, 2)), 2: ((3, 2), (2, 2))}
    granted = bb.resolve_moves(proposals, priority={1: 5, 2: 1},
                               alternatives={2: [(3, 3)]})
    assert granted[1] == (3, 2)
    assert granted[2] == (3, 3)          # side step instead of swapping through
    assert bb.counters["swaps_blocked"] == 1


def test_wait_cascades_to_followers():
    bb = Blackboard()
    # 1 is blocked by 3 (staying), so 2, which follows 1, must wait too
    proposals = {1: ((1, 0), (2, 0)), 2: ((0, 0), (1, 0)), 3: ((2, 0), (2, 0))}
    granted = bb.resolve_moves(proposals, priority={1: 1, 2: 1, 3: 0})
    assert granted == {1: (1, 0), 2: (0, 0), 3: (2, 0)}


def test_task_lifecycle():
    bb = Blackboard()
    t = bb.post_task((4, 4, 1))
    assert t.status == OPEN and bb.active_task_for_cell((4, 4)) is t
    assert bb.claim(t, 7)
    assert not bb.claim(bb.post_task((1, 1, 1)), 7)   # one task per robot
    bb.mark_picked(7)
    assert t.status == PICKED
    bb.complete(7)
    assert t.status == DONE and bb.delivered[7] == 1
    assert bb.active_task_for_cell((4, 4)) is None


# ------------------------------------------------------------ auction
class R:
    def __init__(self, rid, cost, levels=(1, 2)):
        self.id, self.cost, self.access_levels = rid, cost, list(levels)


def test_lowest_bid_wins_and_each_robot_gets_one_task():
    bb = Blackboard()
    t1 = bb.post_task((1, 1, 1))
    t2 = bb.post_task((2, 2, 1))
    robots = [R(0, 9.0), R(1, 3.0), R(2, 5.0)]
    auc = Auctioneer(bb, cost_fn=lambda r, t: r.cost)
    awards = auc.run_round(robots)
    assert [(t.id, r.id) for t, r, _ in awards] == [(t1.id, 1), (t2.id, 2)]
    assert t1.status == CLAIMED and t1.claimed_by == 1
    assert set(t1.bids) == {0, 1, 2}


def test_ineligible_or_unreachable_robots_do_not_bid():
    bb = Blackboard()
    t = bb.post_task((1, 1, 3))
    robots = [R(0, 1.0, levels=(1, 2)), R(1, INF, levels=(3, 4)), R(2, 8.0, levels=(3, 4))]
    auc = Auctioneer(bb, cost_fn=lambda r, t: r.cost,
                     eligible_fn=lambda r, t: t.level in r.access_levels)
    awards = auc.run_round(robots)
    assert awards[0][1].id == 2
    assert set(t.bids) == {2}


def test_timeout_triggers_reauction_to_another_robot():
    bb = Blackboard()
    t = bb.post_task((1, 1, 1))
    robots = [R(0, 2.0), R(1, 4.0)]
    auc = Auctioneer(bb, cost_fn=lambda r, t: r.cost, deadline_base=5, deadline_per_cell=0)
    auc.run_round(robots)
    assert t.claimed_by == 0
    bb.tick(10)
    expired = auc.expired()
    assert expired == [t]
    auc.release(t, "timeout")
    assert t.status == OPEN and bb.counters["timeouts"] == 1
    auc.run_round(robots)
    assert t.claimed_by == 1          # failed robot excluded although it bids lower
    assert t.attempts == 2


# ------------------------------------------------------------ integration
def _run(allocation, conflict, steps=60, seed=3):
    from warehouse import Warehouse
    random.seed(seed)
    np.random.seed(seed)
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            m = Warehouse(parameters={"config_path": "layout.json",
                                      "allocation_mode": allocation,
                                      "conflict_mode": conflict})
            m.setup()
            m.epsilon_override = 0.05
            for _ in range(steps):
                m.step()
    finally:
        os.chdir(cwd)
    return m


@pytest.mark.parametrize("allocation,conflict", [("greedy", "legacy"), ("auction", "blackboard")])
def test_short_seeded_episode_runs(allocation, conflict):
    m = _run(allocation, conflict)
    assert m.stats["step"] == 60
    env = m.serialize_for_unity()
    assert {"ticks", "episode_done", "robots", "boxes", "actions"} <= set(env["state"])
    coord = env["state"]["coordination"]
    assert coord["allocation_mode"] == allocation
    assert "tasks" in coord["blackboard"]


def test_auction_mode_uses_blackboard_tasks():
    m = _run("auction", "blackboard", steps=40)
    bb = m.blackboard
    assert bb.counters["tasks_posted"] >= 1 and bb.counters["awards"] >= 1
    # no box is claimed by two robots at once
    cells = [t.cell for t in bb.claimed_tasks()]
    assert len(cells) == len(set(cells))
    # robots with a claimed task carry the matching box location
    for t in bb.claimed_tasks():
        rb = next(r for r in m.robots if r.id == t.claimed_by)
        assert tuple(rb.box_location[:2]) == t.cell
    assert m.stats["collisions"] == 0


def test_api_exposes_blackboard_without_breaking_contract():
    pytest.importorskip("httpx")
    try:
        from fastapi import FastAPI
        FastAPI()
    except TypeError:
        pytest.skip("installed fastapi/starlette versions are incompatible; use requirements-dev.txt")
    from fastapi.testclient import TestClient
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        import unity_api
        with contextlib.redirect_stdout(io.StringIO()):
            client = TestClient(unity_api.app)
            assert client.post("/start").json()["ok"] is True
            env = client.post("/step?steps=5").json()
            bb = client.get("/blackboard").json()
    finally:
        os.chdir(cwd)
    assert env["initialized"] is True
    robot = env["state"]["robots"][0]
    assert {"id", "x", "y", "heading", "action"} <= set(robot) and "task_id" in robot
    assert env["state"]["coordination"]["allocation_mode"] == "auction"
    assert bb["blackboard"]["counters"]["tasks_posted"] >= 1
