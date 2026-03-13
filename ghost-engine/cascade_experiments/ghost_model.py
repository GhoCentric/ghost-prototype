# ghost_model.py

from copy import deepcopy
from config import CITIES,INITIAL_WEIGHTS,TICKS,ALPHA,BETA,GAMMA,K1,K2,LAMBDA,DELTA,MU,COLLAPSE_THRESHOLD,init_state

def run_ghost(sabotage_level=0.3,use_memory=True,use_nonlinear=True,use_topology=True):
    state=init_state()
    W=deepcopy(INITIAL_WEIGHTS)
    logs=[]

    for tick in range(TICKS):
        loss={city:0.0 for city in CITIES}

        if tick==0:
            loss["C0"]+=sabotage_level
            loss["C1"]+=sabotage_level

        spread={}
        for i in CITIES:
            s=0.0
            for j in CITIES:
                if (j,i) in W:

                    # 🔥 collapse amplifier
                    mult = 1.8 if state[j]["collapsed"] else 1.0

                    s += state[j]["tension"] * W[(j,i)] * ALPHA * mult

            spread[i]=s

        for city in CITIES:
            if state[city]["collapsed"]:
                continue
            
            # 🔥 collapsed neighbors continuously generate pressure
            collapse_pressure = sum(
                0.02 for n in CITIES
                if n != city and state[n]["collapsed"]
            )
            loss[city] += collapse_pressure
            
            if use_memory:
                state[city]["memory"]=GAMMA*state[city]["memory"]+loss[city]
                pressure_source=state[city]["memory"]
            else:
                state[city]["memory"]=0.0
                pressure_source=loss[city]

            base=K1*pressure_source+K2*spread[city]

            if use_nonlinear:
                amp=base*(1.0+LAMBDA*(state[city]["tension"]**2))
            else:
                amp=base

            state[city]["tension"]+=amp
            state[city]["tension"]=min(1.0,state[city]["tension"])

            neighbor_memory_avg=sum(
                state[n]["memory"] for n in CITIES if n!=city
            )/2.0

            state[city]["stability"]-=BETA*(state[city]["tension"]+MU*neighbor_memory_avg)
            state[city]["stability"]=max(0.0,state[city]["stability"])

            if state[city]["stability"]<COLLAPSE_THRESHOLD:
                state[city]["collapsed"]=True

                if use_topology:
                    for k in CITIES:
                        if (city,k) in W:
                            W[(city,k)]*=0.6
                        if (k,city) in W:
                            W[(k,city)]*=0.6

                    for n in CITIES:
                        if n!=city:
                            state[n]["memory"]=min(1.0,state[n]["memory"]+DELTA)

        logs.append(deepcopy(state))

    return logs
