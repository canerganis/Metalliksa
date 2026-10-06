#!/usr/bin/env python3
from __future__ import annotations
import math, time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm as scipy_norm

_DEFAULT_BOUNDS = dict(
    laserPower_W=(100.0,500.0),
    scanSpeed_mms=(200.0,2000.0),
    hatch_um=(60.0,200.0),
    layer_um=(20.0,80.0),
)
_PARAM_KEYS = list(_DEFAULT_BOUNDS)

def _norm(x, bounds): return (x-bounds[:,0])/(bounds[:,1]-bounds[:,0]+1e-15)
def _denorm(X, bounds): return X*(bounds[:,1]-bounds[:,0])+bounds[:,0]

class GaussianProcessSurrogate:
    def __init__(self, n_dims, noise_sigma=1e-3):
        self.n_dims=n_dims; self.noise_sigma=noise_sigma
        self._log_theta=np.zeros(1+n_dims)
        self.X_train=self.y_train=self._L=self._alpha=None
        self._y_mean=0.0; self._y_std=1.0

    def _kernel(self, X1, X2, lt):
        sf=math.exp(lt[0]); ls=np.exp(lt[1:])
        d=(X1[:,None,:]-X2[None,:,:])/ls
        return sf**2*np.exp(-0.5*np.sum(d**2,axis=-1))

    def _lml(self, lt):
        if self.X_train is None: return 0.0
        K=self._kernel(self.X_train,self.X_train,lt)
        K+=(self.noise_sigma**2+1e-8)*np.eye(len(self.X_train))
        try: L=np.linalg.cholesky(K)
        except np.linalg.LinAlgError: return -1e10
        a=np.linalg.solve(L.T,np.linalg.solve(L,self.y_train))
        return float(-0.5*self.y_train@a-np.sum(np.log(np.diag(L)))-0.5*len(self.y_train)*math.log(2*math.pi))

    def fit(self, X, y):
        self.X_train=X.copy()
        self._y_mean,self._y_std=float(y.mean()),float(y.std()+1e-10)
        self.y_train=(y-self._y_mean)/self._y_std
        res=minimize(lambda lt:-self._lml(lt),self._log_theta,method='L-BFGS-B',
                     bounds=[(-3,3)]*(1+self.n_dims),options={'maxiter':50})
        self._log_theta=res.x
        K=self._kernel(self.X_train,self.X_train,self._log_theta)
        K+=(self.noise_sigma**2+1e-8)*np.eye(len(self.X_train))
        self._L=np.linalg.cholesky(K)
        self._alpha=np.linalg.solve(self._L.T,np.linalg.solve(self._L,self.y_train))
        return self

    def predict(self, X_star):
        if self.X_train is None:
            return np.zeros(len(X_star))*self._y_std+self._y_mean, np.ones(len(X_star))*self._y_std
        Ks=self._kernel(X_star,self.X_train,self._log_theta)
        mu_n=Ks@self._alpha
        v=np.linalg.solve(self._L,Ks.T)
        Kss=np.diag(self._kernel(X_star,X_star,self._log_theta))
        var_n=np.maximum(Kss-np.sum(v**2,axis=0),0.0)
        return mu_n*self._y_std+self._y_mean, np.sqrt(var_n)*self._y_std

def expected_improvement(Xc, gp, best, xi=0.01):
    mu,sigma=gp.predict(Xc)
    sigma=np.maximum(sigma,1e-10)
    z=(mu-best-xi)/sigma
    ei=sigma*(z*scipy_norm.cdf(z)+scipy_norm.pdf(z))
    ei[sigma<1e-10]=0.0
    return ei

class BayesianProcessOptimizer:
    def __init__(self, alloy_id, objective_fn, param_bounds=None, n_warmup=5, seed=42):
        self.alloy_id=alloy_id; self.objective_fn=objective_fn; self.n_warmup=n_warmup
        self.rng=np.random.default_rng(seed)
        merged={**_DEFAULT_BOUNDS, **(param_bounds or {})}
        self.bounds=np.array([merged[k] for k in _PARAM_KEYS])
        self.gp=GaussianProcessSurrogate(n_dims=4)
        self._X_obs=[];self._y_obs=[];self._history=[];self._n=0

    def _pack(self, p): return _norm(np.array([p[k] for k in _PARAM_KEYS]),self.bounds)
    def _unpack(self, x): return {k:float(v) for k,v in zip(_PARAM_KEYS,_denorm(x,self.bounds))}

    def suggest_next(self):
        if len(self._X_obs)<self.n_warmup: return self._unpack(self.rng.random(4))
        X,y=np.array(self._X_obs),np.array(self._y_obs)
        self.gp.fit(X,y); best=float(np.max(y))
        Xc=self.rng.random((6000,4))
        ei=expected_improvement(Xc,self.gp,best)
        x0=Xc[int(np.argmax(ei))]
        res=minimize(lambda x:-float(np.asarray(expected_improvement(x[None,:],self.gp,best)).ravel()[0]),
                     x0,method='L-BFGS-B',bounds=[(0,1)]*4,options={'maxiter':30})
        return self._unpack(np.clip(res.x,0.0,1.0))

    def observe(self, params, score):
        self._X_obs.append(self._pack(params)); self._y_obs.append(score); self._n+=1
        self._history.append({'iteration':self._n,'params':{k:round(params[k],2) for k in _PARAM_KEYS},'score':round(score,4)})

    def best_params(self):
        if not self._y_obs: return None
        return self._history[int(np.argmax(self._y_obs))]

    @property
    def history(self): return list(self._history)

MAX_ITERATIONS = 30
DEFAULT_BEAM_DIAMETER_UM = 80.0
DEFAULT_PREHEAT_TEMP_C = 80.0


def _refuse(kind, message):
    return {'success': False, 'errorKind': kind, 'error': message}


def run_bayesian_optimization(alloy_id, param_bounds=None, n_iter=20, n_warmup=5, seed=42,
                              beam_diameter_um=DEFAULT_BEAM_DIAMETER_UM,
                              preheat_temp_C=DEFAULT_PREHEAT_TEMP_C):
    """Expected-improvement search over (P, v, h, t).

    Objective (unchanged): three-level verdict score (compose_verdict -> _verdict_score) multiplied by the
    normalised volumetric-rate proxy v*h/(v_max*h_max). Unknown alloys, invalid inputs and solver errors are
    returned as explicit failures (errorKind 'validation' or 'solver'); nothing is silently substituted or
    scored as 0.
    """
    from four_alloy_materials import resolve_alloy_id
    from lpbf_thermal_solver import calculate_meltpool_physics
    from lpbf_build_job_solver import compose_verdict
    from lpbf_screening_uq import _verdict_score as verdict_score
    if alloy_id is None or str(alloy_id).strip() == '':
        return _refuse('validation', 'alloyId is required; no default alloy is assumed.')
    resolved = resolve_alloy_id(alloy_id)
    if resolved is None:
        return _refuse('validation', f"Unknown alloy '{alloy_id}': not resolvable by four_alloy_materials; no fallback alloy is used.")
    try:
        n_iter = int(n_iter); n_warmup = int(n_warmup)
        beam = float(beam_diameter_um); preheat = float(preheat_temp_C)
    except (TypeError, ValueError):
        return _refuse('validation', 'nIterations, nWarmup, beamDiameter_um and preheatTemp_C must be numbers.')
    if not (1 <= n_iter <= MAX_ITERATIONS):
        return _refuse('validation', f'nIterations must be between 1 and {MAX_ITERATIONS} (got {n_iter}); it is not silently clamped.')
    if n_warmup < 1:
        return _refuse('validation', 'nWarmup must be at least 1.')
    if not (math.isfinite(beam) and beam > 0):
        return _refuse('validation', 'beamDiameter_um must be a positive finite number.')
    if not (math.isfinite(preheat) and preheat >= 0):
        return _refuse('validation', 'preheatTemp_C must be a finite number >= 0.')
    merged = {**_DEFAULT_BOUNDS, **(param_bounds or {})}
    try:
        for k in _PARAM_KEYS:
            lo, hi = float(merged[k][0]), float(merged[k][1])
            if not (math.isfinite(lo) and math.isfinite(hi) and 0 < lo < hi):
                raise ValueError(k)
            merged[k] = (lo, hi)
    except (TypeError, ValueError, KeyError, IndexError) as e:
        return _refuse('validation', f'Invalid bounds for {e}: each needs finite 0 < min < max.')
    v_max, h_max = merged['scanSpeed_mms'][1], merged['hatch_um'][1]

    def _obj(params):
        th = calculate_meltpool_physics(
            material_name=resolved,
            laser_power_W=float(params['laserPower_W']),
            scan_speed_mm_s=float(params['scanSpeed_mms']),
            beam_diameter_um=beam,
            preheat_temp_C=preheat,
            layer_thickness_um=float(params['layer_um']),
            hatch_spacing_um=float(params['hatch_um']),
            laser_wavelength='IR_1064nm')
        vd = compose_verdict(th, resolved)
        vs = verdict_score(vd['verdict'])
        prod = (float(params['scanSpeed_mms']) * float(params['hatch_um'])) / (v_max * h_max)
        return float(vs) * float(prod), vd['verdict']

    opt = BayesianProcessOptimizer(resolved, None, param_bounds=merged, n_warmup=n_warmup, seed=seed)
    t0 = time.time(); iters = []
    try:
        for i in range(n_iter):
            sug = opt.suggest_next(); sc, verd = _obj(sug); opt.observe(sug, sc)
            iters.append({'iteration': i + 1, 'params': {k: round(sug[k], 2) for k in _PARAM_KEYS},
                          'score': round(sc, 4), 'verdict': verd})
    except Exception as e:
        return _refuse('solver', f'Solver failed at iteration {len(iters) + 1}: {type(e).__name__}: {e}')
    elapsed = round((time.time() - t0) * 1000.0, 1)
    best = opt.best_params()
    recent = [it['score'] for it in iters[-5:]]
    converged = len(recent) >= 5 and (max(recent) - min(recent)) < 1e-3
    return {'success': True, 'alloyId': resolved, 'bestParams': best['params'] if best else None,
            'bestScore': round(max(it['score'] for it in iters), 4),
            'iterations': iters, 'converged': converged, 'elapsedMs': elapsed, 'nIterations': n_iter,
            'nWarmup': n_warmup, 'beamDiameter_um': beam, 'preheatTemp_C': preheat,
            'objective': 'three-level verdict score x normalised v*h (v*h / (v_max*h_max))'}


def optimize_process_window(alloy_id="in718", bounds=None, param_bounds=None, n_iterations=20, n_iter=None, n_initial=5, n_warmup=None, seed=42):
    """Convenience alias supporting both naming conventions."""
    b = bounds if bounds is not None else param_bounds
    ni = n_iter if n_iter is not None else n_iterations
    nw = n_warmup if n_warmup is not None else n_initial
    return run_bayesian_optimization(alloy_id=alloy_id, param_bounds=b, n_iter=ni, n_warmup=nw, seed=seed)


def main():
    import json, sys
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({'error': 'Empty payload.'}))
        sys.exit(1)
    try:
        data = json.loads(raw)
    except Exception as e:
        print(json.dumps({'error': f'Invalid JSON: {e}'}))
        sys.exit(1)
    result = run_bayesian_optimization(
        alloy_id=data.get('alloyId'),
        param_bounds=data.get('paramBounds'),
        n_iter=data.get('nIterations', 20),
        n_warmup=data.get('nWarmup', 5),
        seed=int(data.get('seed', 42)),
        beam_diameter_um=data.get('beamDiameter_um', DEFAULT_BEAM_DIAMETER_UM),
        preheat_temp_C=data.get('preheatTemp_C', DEFAULT_PREHEAT_TEMP_C),
    )
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__':
    main()
