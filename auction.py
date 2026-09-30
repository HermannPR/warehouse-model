"""Contract-Net style task allocation on top of the Blackboard.

Round, run once per tick while there are open tasks and idle robots:
1. announce: each OPEN task on the blackboard is announced (oldest first).
2. bid: every idle, eligible robot sends a cost estimate for the task.
   The cost function is injected (the Warehouse model supplies one based on
   A* path length, battery and congestion read from the blackboard).
3. award: lowest bid wins (ties broken by robot id); the winner claims the
   task on the blackboard and drops out of the round.
4. monitor: a claimed task that is not picked up within its deadline is
   released and re-auctioned; the robot that failed it is excluded from
   the next round for that task (unless it is the only eligible bidder).

Q-learning still decides how each robot moves; the auction only decides
which robot takes which task.
"""
from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Tuple

from blackboard import Blackboard, Task, CLAIMED

INF = float("inf")


class Auctioneer:
    def __init__(self, blackboard: Blackboard,
                 cost_fn: Callable[[object, Task], float],
                 eligible_fn: Callable[[object, Task], bool] = lambda r, t: True,
                 robot_id: Callable[[object], int] = lambda r: int(r.id),
                 deadline_base: int = 40, deadline_per_cell: float = 3.0):
        self.bb = blackboard
        self.cost_fn = cost_fn
        self.eligible_fn = eligible_fn
        self.robot_id = robot_id
        self.deadline_base = int(deadline_base)
        self.deadline_per_cell = float(deadline_per_cell)
        self.deadlines: Dict[int, int] = {}   # task_id -> step limit for pickup

    def run_round(self, idle_robots: Iterable[object]) -> List[Tuple[Task, object, float]]:
        """Announce open tasks, collect bids, award winners. Returns the awards."""
        pool = list(idle_robots)
        awards: List[Tuple[Task, object, float]] = []
        for task in self.bb.open_tasks():
            if not pool:
                break
            self.bb.announce(task)
            bids: List[Tuple[float, int, object]] = []
            for rb in pool:
                if not self.eligible_fn(rb, task):
                    continue
                cost = float(self.cost_fn(rb, task))
                if cost == INF:
                    continue
                self.bb.record_bid(task, self.robot_id(rb), cost)
                bids.append((cost, self.robot_id(rb), rb))
            if not bids:
                continue
            # Prefer robots that have not already failed this task
            fresh = [b for b in bids if b[1] not in task.excluded]
            cost, rid, winner = min(fresh or bids, key=lambda b: (b[0], b[1]))
            if self.bb.claim(task, rid):
                task.excluded.clear()
                self.deadlines[task.id] = self.bb.step + self.deadline_base + int(self.deadline_per_cell * cost)
                pool.remove(winner)
                awards.append((task, winner, cost))
        return awards

    def expired(self) -> List[Task]:
        """Claimed (not yet picked) tasks whose pickup deadline has passed."""
        out = []
        for t in self.bb.claimed_tasks():
            if t.status == CLAIMED and self.bb.step > self.deadlines.get(t.id, INF):
                out.append(t)
        return out

    def release(self, task: Task, reason: str) -> None:
        self.deadlines.pop(task.id, None)
        self.bb.release(task, reason)
