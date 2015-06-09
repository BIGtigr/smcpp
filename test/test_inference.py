import pytest
import multiprocessing
import numpy as np
import logging

logging.getLogger().setLevel("INFO")

import inference
from fixtures import *

N = 10
L = 100
hidden_states = np.array([0.0, 0.5, 1.0, 2.0, 3.0, 4.0, np.inf])
NTHREADS = 2

def test_loglik_diff_nodiff(demo, fake_obs):
    a, b, s = demo
    S = 100
    M = 10
    N0 = 1000.
    rho = theta = 1e-8
    obs_list = [fake_obs]
    def f(a, b, s, jacobian):
        return inference.loglik(
                [a, b, s],
                N,
                S, M,
                obs_list, # List of the observations datasets we prepared above
                hidden_states,
                N0 * rho, # Same parameters as above
                N0 * theta, 
                reg=0.,
                numthreads=NTHREADS, seed=1, viterbi=False, jacobian=jacobian)
    logp, jac = f(a, b, s, True)
    logp2 = f(a, b, s, False)
    print(logp, logp2)
    print(jac)
    aoeu

def test_derivatives(demo, fake_obs):
    x, y = demo
    S = 1000
    M = 100
    N0 = 1000.
    rho = theta = 1e-8
    obs_list = [fake_obs]
    def f(x, y, jacobian):
        return inference.loglik(
                x, y,
                N,
                S, M,
                obs_list, # List of the observations datasets we prepared above
                hidden_states,
                N0 * rho, # Same parameters as above
                N0 * theta, 
                reg=0.,
                numthreads=NTHREADS, seed=1, viterbi=False, jacobian=jacobian)
    logp, jac = f(x, y, True)
    print(jac)
    eps = 0.1
    K = len(x)
    I = np.eye(K)
    for k in [0, 1]:
        for ell in range(K):
            args = [x.copy(), y.copy()]
            args[k][ell] += eps
            logp2 = f(args[0], args[1], False)
            print(k, ell, logp2, logp, jac[k, ell], logp2 - (logp + eps * jac[k, ell]))

def test_inference_parallel(constant_demo_1, fake_obs):
    a, b, s = constant_demo_1
    ll, jac = inference.loglik(a, b, s, 1, 1, N, [fake_obs,] * 4, 1e-8, 1e-8, hidden_states, numthreads=8, jacobian=True)
    print(ll)
    print(jac)
    # Well, that worked
