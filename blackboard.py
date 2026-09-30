"""Shared knowledge store (Blackboard) for the warehouse robots.

Every robot and the model's coordination layer read and write facts here
instead of talking to each other directly:

- tasks: boxes waiting to be picked (OPEN), announced for auction, CLAIMED by a
  robot, PICKED (box on board), DONE or released after a failure.
- robot positions and intents (the cell each robot wants to occupy next tick).
- cell reservations for the next tick, used to resolve movement conflicts
  (many-to-one merges, occupant-stays and head-on swaps).
- congestion heat per cell (decaying counter of contested cells).
- delivered counts per robot and a short event log.

The class has no dependency on agentpy or the Warehouse model, so it can be
unit tested in isolation.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

Cell = Tuple[int, int]

OPEN = "OPEN"
ANNOUNCED = "ANNOUNCED"
CLAIMED = "CLAIMED"
PICKED = "PICKED"
DONE = "DONE"

ACTIVE_STATUSES = (OPEN, ANNOUNCED, CLAIMED, PICKED)


@dataclass
class Task:
    id: int
    box: Tuple[int, int, int]           # (x, y, level)
    created_step: int
    status: str = OPEN
    claimed_by: Optional[int] = None
    claimed_step: Optional[int] = None
    attempts: int = 0                   # how many times it was awarded
    bids: Dict[int, float] = field(default_factory=dict)
    excluded: Set[int] = field(default_factory=set)   # robots that failed it
    done_step: Optional[int] = None

    @property
    def cell(self) -> Cell:
        return (int(self.box[0]), int(self.box[1]))

    @property
    def level(self) -> int:
        return int(self.box[2]) if len(self.box) > 2 else 1

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "box": [int(v) for v in self.box],
            "status": self.status,
            "claimed_by": self.claimed_by,
            "attempts": self.attempts,
            "bids": [{"robot_id": int(r), "cost": round(float(c), 2)}
                     for r, c in sorted(self.bids.items(), key=lambda kv: kv[1])],
        }


class Blackboard:
    def __init__(self, congestion_decay: float = 0.9, log_size: int = 50):
        self.step = 0
        self.tasks: Dict[int, Task] = {}
        self._next_task_id = 1
        self.robot_positions: Dict[int, Cell] = {}
        self.intents: Dict[int, Cell] = {}
        self.reservations: Dict[Cell, int] = {}
        self.congestion: Dict[Cell, float] = {}
        self.congestion_decay = float(congestion_decay)
        self.delivered: Dict[int, int] = {}
        self.events: deque = deque(maxlen=log_size)
        self.counters = {
            "tasks_posted": 0,
            "awards": 0,
            "reauctions": 0,
            "timeouts": 0,
            "stuck_releases": 0,
            "reservation_waits": 0,
            "swaps_blocked": 0,
        }

    # ------------------------------------------------------------------ log
    def log(self, kind: str, **data) -> None:
        entry = {"step": self.step, "event": kind}
        entry.update(data)
        self.events.append(entry)

    def tick(self, step: int) -> None:
        """Start a new tick: decay congestion and clear last tick's reservations."""
        self.step = int(step)
        self.reservations = {}
        self.intents = {}
        for cell in list(self.congestion):
            v = self.congestion[cell] * self.congestion_decay
            if v < 0.05:
                del self.congestion[cell]
            else:
                self.congestion[cell] = v

    # ---------------------------------------------------------------- tasks
    def post_task(self, box: Iterable[int]) -> Task:
        box = tuple(int(v) for v in box)
        if len(box) == 2:
            box = (box[0], box[1], 1)
        task = Task(id=self._next_task_id, box=box, created_step=self.step)
        self._next_task_id += 1
        self.tasks[task.id] = task
        self.counters["tasks_posted"] += 1
        self.log("post", task=task.id, box=list(box))
        return task

    def active_task_for_cell(self, cell: Cell) -> Optional[Task]:
        cell = (int(cell[0]), int(cell[1]))
        for t in self.tasks.values():
            if t.status in ACTIVE_STATUSES and t.cell == cell:
                return t
        return None

    def open_tasks(self) -> List[Task]:
        return sorted((t for t in self.tasks.values() if t.status in (OPEN, ANNOUNCED)),
                      key=lambda t: (t.created_step, t.id))

    def claimed_tasks(self) -> List[Task]:
        return [t for t in self.tasks.values() if t.status in (CLAIMED, PICKED)]

    def task_of(self, robot_id: int) -> Optional[Task]:
        for t in self.tasks.values():
            if t.claimed_by == robot_id and t.status in (CLAIMED, PICKED):
                return t
        return None

    def announce(self, task: Task) -> None:
        task.status = ANNOUNCED
        task.bids = {}

    def record_bid(self, task: Task, robot_id: int, cost: float) -> None:
        task.bids[int(robot_id)] = float(cost)

    def claim(self, task: Task, robot_id: int) -> bool:
        if task.status not in (OPEN, ANNOUNCED):
            return False
        if self.task_of(robot_id) is not None:
            return False  # one task per robot
        task.status = CLAIMED
        task.claimed_by = int(robot_id)
        task.claimed_step = self.step
        task.attempts += 1
        self.counters["awards"] += 1
        self.log("award", task=task.id, robot=int(robot_id),
                 cost=round(task.bids.get(int(robot_id), 0.0), 2))
        return True

    def mark_picked(self, robot_id: int) -> Optional[Task]:
        t = self.task_of(robot_id)
        if t is not None and t.status == CLAIMED:
            t.status = PICKED
            self.log("picked", task=t.id, robot=int(robot_id))
        return t

    def complete(self, robot_id: int) -> Optional[Task]:
        t = self.task_of(robot_id)
        if t is None:
            return None
        t.status = DONE
        t.done_step = self.step
        self.delivered[int(robot_id)] = self.delivered.get(int(robot_id), 0) + 1
        self.log("delivered", task=t.id, robot=int(robot_id))
        return t

    def release(self, task: Task, reason: str) -> None:
        """Put a claimed task back on the market (re-auction on next round)."""
        if task.status != CLAIMED:
            return
        if task.claimed_by is not None:
            task.excluded.add(task.claimed_by)
        self.log("release", task=task.id, robot=task.claimed_by, reason=reason)
        task.status = OPEN
        task.claimed_by = None
        task.claimed_step = None
        task.bids = {}
        self.counters["reauctions"] += 1
        if reason == "timeout":
            self.counters["timeouts"] += 1
        elif reason == "stuck":
            self.counters["stuck_releases"] += 1

    def prune_done(self, keep: int = 20) -> None:
        done = sorted((t for t in self.tasks.values() if t.status == DONE),
                      key=lambda t: t.id)
        for t in done[:-keep] if keep else done:
            del self.tasks[t.id]

    # --------------------------------------------------- robots and motion
    def update_robot(self, robot_id: int, pos: Cell) -> None:
        self.robot_positions[int(robot_id)] = (int(pos[0]), int(pos[1]))

    def add_congestion(self, cell: Cell, amount: float = 1.0) -> None:
        cell = (int(cell[0]), int(cell[1]))
        self.congestion[cell] = self.congestion.get(cell, 0.0) + float(amount)

    def congestion_at(self, cell: Cell) -> float:
        return self.congestion.get((int(cell[0]), int(cell[1])), 0.0)

    def resolve_moves(self, proposals: Dict[int, Tuple[Cell, Cell]],
                      priority: Dict[int, float],
                      alternatives: Optional[Dict[int, List[Cell]]] = None) -> Dict[int, Cell]:
        """Grant next-cell reservations. Returns robot_id -> granted next cell.

        proposals:    robot_id -> (current_cell, desired_next_cell)
        priority:     robot_id -> priority (higher wins)
        alternatives: robot_id -> ordered fallback cells (side steps) to try
                      when the desired cell cannot be granted.

        Rules, applied until a fixed point is reached:
        1. A robot that stays in place reserves its own cell first (occupant stays).
        2. Movers claim their target cell in priority order; if it is already
           reserved (many-to-one merge) they try their next fallback cell.
        3. A mover whose target is the current cell of a granted mover that is
           heading into its own cell (head-on swap) also falls back.
        4. With no fallback left the robot waits, reserves its current cell,
           and the pass is repeated because that can block other movers.
        A granted cell equal to the current cell means WAIT.
        """
        alternatives = alternatives or {}
        options: Dict[int, List[Cell]] = {}
        for rid, (cur, nxt) in proposals.items():
            if nxt == cur:
                options[rid] = []   # chose to stay (WAIT, PICKUP, ...): no side steps
                continue
            opts = [nxt] + [c for c in alternatives.get(rid, []) if c != cur and c != nxt]
            options[rid] = opts
        choice = {rid: 0 for rid in proposals}

        def wants(rid):
            opts = options[rid]
            return opts[choice[rid]] if choice[rid] < len(opts) else proposals[rid][0]

        swaps: Set[Tuple[int, int]] = set()
        reserved: Dict[Cell, int] = {}
        for _ in range(sum(len(o) for o in options.values()) + 2):
            reserved = {}
            staying = [rid for rid in proposals if wants(rid) == proposals[rid][0]]
            for rid in staying:
                reserved[proposals[rid][0]] = rid
            movers = sorted((rid for rid in proposals if rid not in staying),
                            key=lambda r: (-priority.get(r, 0.0), r))
            granted: Dict[int, Cell] = {}
            bumped = None
            for rid in movers:
                cur, nxt = proposals[rid][0], wants(rid)
                if nxt in reserved:
                    bumped = rid
                    self.add_congestion(nxt)
                    break
                swap_with = next((o for o, dest in granted.items()
                                  if dest == cur and proposals[o][0] == nxt), None)
                if swap_with is not None:
                    bumped = rid
                    swaps.add(tuple(sorted((rid, swap_with))))
                    self.add_congestion(nxt)
                    break
                reserved[nxt] = rid
                granted[rid] = nxt
            if bumped is None:
                break
            choice[bumped] += 1
        result = {rid: wants(rid) for rid in proposals}
        self.reservations = reserved
        self.intents = dict(result)
        forced = [rid for rid, (cur, nxt) in proposals.items() if nxt != cur and result[rid] == cur]
        self.counters["reservation_waits"] += len(forced)
        self.counters["swaps_blocked"] += len(swaps)
        return result

    # ------------------------------------------------------------ snapshot
    def snapshot(self, max_events: int = 10) -> dict:
        tasks = sorted(self.tasks.values(), key=lambda t: t.id)
        hot = sorted(self.congestion.items(), key=lambda kv: -kv[1])[:10]
        return {
            "step": self.step,
            "tasks": [t.to_dict() for t in tasks if t.status != DONE],
            "reservations": [{"robot_id": int(r), "cell": [int(c[0]), int(c[1])]}
                             for c, r in sorted(self.reservations.items(), key=lambda kv: kv[1])],
            "intents": [{"robot_id": int(r), "cell": [int(c[0]), int(c[1])]}
                        for r, c in sorted(self.intents.items())],
            "congestion": [{"cell": [int(c[0]), int(c[1])], "heat": round(float(h), 2)}
                           for c, h in hot],
            "delivered": {str(k): int(v) for k, v in sorted(self.delivered.items())},
            "counters": dict(self.counters),
            "events": list(self.events)[-max_events:],
        }
