# compare_runs.py

from control_model import run_control
from ghost_model import run_ghost

def collapse_timeline(logs):
    out={}
    for tick,state in enumerate(logs):
        for city in state:
            if state[city]["collapsed"] and city not in out:
                out[city]=tick
    return out

def final_snapshot(logs):
    return logs[-1]

sabotage=0.7

control_logs=run_control(sabotage)
ghost_full=run_ghost(sabotage,use_memory=True,use_nonlinear=True,use_topology=True)
ghost_no_memory=run_ghost(sabotage,use_memory=False,use_nonlinear=True,use_topology=True)
ghost_no_nonlinear=run_ghost(sabotage,use_memory=True,use_nonlinear=False,use_topology=True)
ghost_no_topology=run_ghost(sabotage,use_memory=True,use_nonlinear=True,use_topology=False)

print("\nCONTROL COLLAPSE:")
print(collapse_timeline(control_logs))

print("\nGHOST FULL COLLAPSE:")
print(collapse_timeline(ghost_full))

print("\nGHOST NO MEMORY COLLAPSE:")
print(collapse_timeline(ghost_no_memory))

print("\nGHOST NO NONLINEAR COLLAPSE:")
print(collapse_timeline(ghost_no_nonlinear))

print("\nGHOST NO TOPOLOGY COLLAPSE:")
print(collapse_timeline(ghost_no_topology))

print("\nCONTROL FINAL:")
print(final_snapshot(control_logs))

print("\nGHOST FULL FINAL:")
print(final_snapshot(ghost_full))

print("\nGHOST NO MEMORY FINAL:")
print(final_snapshot(ghost_no_memory))

print("\nGHOST NO NONLINEAR FINAL:")
print(final_snapshot(ghost_no_nonlinear))

print("\nGHOST NO TOPOLOGY FINAL:")
print(final_snapshot(ghost_no_topology))
