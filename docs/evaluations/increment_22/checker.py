"""Independent exact checker for the custom Increment 22 scheduling task."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any


TASK = Path(__file__).with_name("task.json")


def verify_schedule(task: dict[str, Any], by_machine: dict[str, list[tuple[str, int, int]]]) -> int:
    jobs = {job["id"]: job for job in task["jobs"]}
    seen: set[str] = set()
    for machine, sequence in by_machine.items():
        previous_end = 0
        for job_id, start, end in sequence:
            assert job_id in jobs and job_id not in seen
            assert machine in jobs[job_id]["machines"]
            assert end - start == jobs[job_id]["duration"]
            assert start >= previous_end
            seen.add(job_id)
            previous_end = end
    assert seen == set(jobs)
    starts = {
        job_id: start
        for sequence in by_machine.values()
        for job_id, start, _ in sequence
    }
    ends = {
        job_id: end
        for sequence in by_machine.values()
        for job_id, _, end in sequence
    }
    for job_id, job in jobs.items():
        assert all(ends[parent] <= starts[job_id] for parent in job["predecessors"])
    return max(ends.values(), default=0)


def earliest_finish(
    jobs: dict[str, dict[str, Any]], machine_orders: dict[str, tuple[str, ...]]
) -> int | None:
    """Return the schedule's earliest finish, or None if its precedence graph cycles."""
    edges = {job_id: set() for job_id in jobs}
    for job_id, job in jobs.items():
        edges[job_id].update(job["predecessors"])
    for order in machine_orders.values():
        for left, right in zip(order, order[1:]):
            edges[right].add(left)

    indegree = {job_id: len(parents) for job_id, parents in edges.items()}
    successors = {job_id: set() for job_id in jobs}
    for child, parents in edges.items():
        for parent in parents:
            successors[parent].add(child)
    ready = [job_id for job_id, count in indegree.items() if count == 0]
    finish: dict[str, int] = {}
    while ready:
        job_id = ready.pop()
        finish[job_id] = max((finish[parent] for parent in edges[job_id]), default=0)
        finish[job_id] += jobs[job_id]["duration"]
        for child in successors[job_id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if len(finish) != len(jobs):
        return None
    return max(finish.values(), default=0)


def exact_minimum(task: dict[str, Any]) -> tuple[int, dict[str, tuple[str, ...]], int]:
    """Enumerate each eligible machine assignment and both machine orders."""
    jobs = {job["id"]: job for job in task["jobs"]}
    ids = tuple(jobs)
    machines = tuple(sorted({machine for job in jobs.values() for machine in job["machines"]}))
    best = sum(job["duration"] for job in jobs.values()) + 1
    witness: dict[str, tuple[str, ...]] | None = None
    checked = 0

    for assignment in itertools.product(*(jobs[job_id]["machines"] for job_id in ids)):
        buckets = {machine: [] for machine in machines}
        for job_id, machine in zip(ids, assignment, strict=True):
            buckets[machine].append(job_id)
        order_options = [tuple(itertools.permutations(buckets[machine])) for machine in machines]
        for orders in itertools.product(*order_options):
            checked += 1
            machine_orders = dict(zip(machines, orders, strict=True))
            value = earliest_finish(jobs, machine_orders)
            if value is not None and value < best:
                best = value
                witness = machine_orders
    assert witness is not None
    return best, witness, checked


def main() -> None:
    task = json.loads(TASK.read_text())
    proposed = {
        machine: [tuple(row) for row in rows]
        for machine, rows in task["proposed_schedule"].items()
        if machine in {"M1", "M2"}
    }
    proposed_makespan = verify_schedule(task, proposed)
    assert proposed_makespan == task["proposed_schedule"]["claimed_makespan"]
    optimum, orders, cases = exact_minimum(task)
    witness = {machine: order for machine, order in orders.items()}
    print(
        json.dumps(
            {
                "checker": "eligible-machine assignments × machine permutations × DAG longest paths",
                "enumerated_machine_assignment_order_cases": cases,
                "proposed_schedule_valid": True,
                "proposed_makespan": proposed_makespan,
                "exact_minimum_makespan": optimum,
                "optimal_machine_orders": witness,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
