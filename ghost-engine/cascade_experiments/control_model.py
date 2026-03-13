# control_model.py

from copy import deepcopy
from config import CITIES,INITIAL_WEIGHTS,TICKS,ALPHA,BETA,GAMMA,K1,K2,COLLAPSE_THRESHOLD,init_state

def run_control(sabotage_level=0.3):
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
                    s+=state[j]["tension"]*W[(j,i)]*ALPHA
            spread[i]=s

        for city in CITIES:
            if state[city]["collapsed"]:
                continue

            state[city]["memory"]=GAMMA*state[city]["memory"]+loss[city]
            state[city]["tension"]+=K1*loss[city]+K2*spread[city]
            state[city]["tension"]=min(1.0,state[city]["tension"])

            state[city]["stability"]-=BETA*state[city]["tension"]
            state[city]["stability"]=max(0.0,state[city]["stability"])

            if state[city]["stability"]<COLLAPSE_THRESHOLD:
                state[city]["collapsed"]=True
                for k in CITIES:
                    if (city,k) in W:
                        W[(city,k)]=0.0

        logs.append(deepcopy(state))

    return logs
