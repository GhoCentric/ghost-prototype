# config.py

import random

CITIES=[f"C{i}" for i in range(12)]

INITIAL_STABILITY=1.0
INITIAL_TENSION=0.05
INITIAL_MEMORY=0.0

COLLAPSE_THRESHOLD=0.3

random.seed(7)

INITIAL_WEIGHTS={}

for i in CITIES:
    for j in CITIES:
        if i!=j and random.random()<0.35:
            INITIAL_WEIGHTS[(i,j)]=round(random.uniform(0.3,1.0),2)

ALPHA=0.025
BETA=0.03
GAMMA=0.85

K1=0.02
K2=0.015

LAMBDA=1.2
DELTA=0.08
MU=0.50

TICKS=250

def init_state():
    return {
        city:{
            "stability":INITIAL_STABILITY,
            "tension":INITIAL_TENSION,
            "memory":INITIAL_MEMORY,
            "collapsed":False,
        }
        for city in CITIES
    }
