'Miscellaneous estimation and data-massaging functions.'
from __future__ import absolute_import, division, print_function
import sys
import numpy as np
from logging import getLogger
logger = getLogger(__name__)
import scipy.optimize
import scipy.interpolate
import multiprocessing
import ad.admath, ad.linalg

from . import _smcpp, util

## 
## Construct time intervals stuff
## 
def extract_pieces(piece_str):
    '''Convert PSMC-style piece string to model representation.'''
    pieces = []
    for piece in piece_str.split("+"):
        try:
            num, span = list(map(int, piece.split("*")))
        except ValueError:
            span = int(piece)
            num = 1
        pieces += [span] * num
    return pieces

def construct_time_points(t1, tK, pieces):
    logger.debug((t1, tK, pieces))
    s = np.logspace(np.log10(t1[-1]), np.log10(tK), sum(pieces) + 1)
    s = s[1:] - s[:-1]
    time_points = np.zeros(len(pieces))
    count = 0
    for i, p in enumerate(pieces):
        time_points[i] = s[count:(count+p)].sum()
        count += p
    return np.concatenate([t1, time_points])

##
## Regularization
##
# This is taken directly from the Wikipedia page


def _pchipendpoint(h1, h2, del1, del2):
    d = ((2 * h1 + h2) * del1 - h1 * del2) / (h1 + h2)
    if np.sign(d) != np.sign(del1):
        d = 0
    elif (np.sign(del1) != np.sign(del2)) and (abs(d) > abs(3 * del1)):
        d = 3 * del1
    return d


def _pchipslopes(h, delta):
    n = len(h) + 1
    d = np.zeros_like(delta)
    k = np.where(np.sign(delta[:(n - 2)]) *
                 np.sign(delta[1:(n + 1)]) > 0)[0] + 1
    w1 = 2 * h[k] + h[k - 1]
    w2 = h[k] + 2 * h[k - 1]
    d[k] = (w1 + w2) / (w1 / delta[k - 1] + w2 / delta[k])
    d[0] = _pchipendpoint(h[0], h[1], delta[0], delta[1])
    d = np.append(d, _pchipendpoint(
        h[n - 2], h[n - 3], delta[n - 2], delta[n - 3]))
    return d


def _pchip(x, y):
    h = np.diff(x)
    delta = np.diff(y) / h
    d = _pchipslopes(h, delta)
    n = len(x)
    c = (3 * delta - 2 * d[:n - 1] - d[1:n]) / h
    b = (d[:n - 1] - 2 * delta + d[1:n]) / h**2
    return b, c, d, y

def regularizer(model, penalty, f, dump_piecewise=False):
    ## Regularizer
    reg = 0
    cs = np.concatenate([[0], np.cumsum(model[2])])
    if f[:3] == "log":
        g = ad.admath.log10
        f = f[3:]
    else:
        g = lambda x: x
    if f in ("quadratic", "abs"):
        for i in range(1, model.K):
            reg += regularizer._regs[f](g(model[0, i - 1]), g(model[0, i]))
        return penalty * reg
    ## Spline fit / curvature penalty
    assert f == "curvature"
    x = np.cumsum(model[2]).astype("float")
    y = np.array([g(_) for _ in model[0]], dtype=object)

    # d2y = np.diff(y, 2)
    # dx = np.diff(x)
    # avgdx = (dx[1:] + dx[:-1]) / 2.
    # curv = d2y / avgdx
    # alpha = 1
    # ecurv = (np.exp(alpha * x)[:-2] * curv**2).sum()
    # return penalty * ecurv

    # dydx = np.diff(y) / np.diff(x)
    # mon = dydx[1:] * dydx[:-1]
    # mon[mon > 0] *= 0
    # return -penalty * mon.sum()
    xy = list(zip(x, y))
    
    xavg = (x[1:] + x[:-1]) / 2.
    yavg = (y[1:] + y[:-1]) / 2.
    xy += list(zip(xavg, yavg))
    pts = sorted(xy)
    x, y = np.array(pts).T

    return penalty * (np.diff(y, 2)**2).sum()
    
    ## Curvature 
    # (d'')^2 = (6au + 2b)^2 = 36a^2 u^2 + 24aub + 4b^2
    # int(d''^2, {u,0,1}) = 36a^2 / 3 + 24ab / 2 + 4b^2
    curv = 0
    for k in range(len(x) - 1):
        a, b = coef[(4 * k):(4 * k + 2)]
        x1, x2 = x[k:(k + 2)]
        xi = x2 - x1
        curv += (12 * a**2 * xi**3 + 12 * a * b * xi**2 + 4 * b**2 * xi)
        print(x1, x2, a, b, curv)
    if dump_piecewise:
        s = "Piecewise[{"
        arr = []
        for k in range(len(x) - 1):
            u = "(x-(%.2f))" % x[k]
            arr.append("{" + "+".join(
                "%.6f*%s^%d" % (float(xi), u, 3 - i) 
                for i, xi in enumerate(coef[(4 * k):(4 * (k + 1))])) + ",x>=%.2f&&x<%.2f}" % (x[k], x[k + 1]))
        s += ",\n".join(arr) + "}];"
        print(s, file=sys.stderr)
        print("curv: %f" % curv, file=sys.stderr)
    return penalty * curv
regularizer._regs = {
        'abs': lambda x, y: abs(x - y),
        'quadratic': lambda x, y: (x - y)**2,
        'logabs': lambda x, y: abs(ad.admath.log(x / y)),
        'logquadratic': lambda x, y: (ad.admath.log(x / y))**2
        }

## TODO: move this to util
def _thin_helper(args):
    thinned = np.array(_smcpp.thin_data(*args), dtype=np.int32)
    return util.compress_repeated_obs(thinned)

def thin_dataset(dataset, thinning):
    '''Only emit full SFS every <thinning> sites'''
    p = multiprocessing.Pool()
    ret = p.map(_thin_helper, [(chrom, thinning, i) for i, chrom in enumerate(dataset)])
    p.close()
    p.join()
    p.terminate()
    return ret
    
def pretrain(model, sample_csfs, bounds, theta0, folded, penalty):
    '''Pre-train model by fitting to observed SFS. Changes model in place!'''
    logger.debug("pretraining")
    n = sample_csfs.shape[1] + 1
    def undist(sfs):
        return util.undistinguished_sfs(sfs, folded)
    sample_sfs = undist(sample_csfs)
    K = model.K
    coords = np.arange(K)
    def f(x):
        x = ad.adnumber(x)
        model[coords] = x
        logger.debug("requesting sfs")
        sfs = _smcpp.raw_sfs(model, n, 0., _smcpp.T_MAX, True)
        sfs[0, 0] = 0
        sfs *= theta0
        sfs[0, 0] = 1. - sfs.sum()
        logger.debug("done")
        usfs = undist(sfs)
        kl = -(sample_sfs * ad.admath.log(usfs)).sum()
        reg = penalty * model.regularizer()
        kl += reg
        ret = (kl.x, np.array(list(map(kl.d, x))))
        logger.debug("\n%s" % np.array_str(np.array([[float(y) for y in row] for row in model._x]), precision=3))
        logger.debug((reg, ret))
        return ret
    x0 = model[coords].astype('float')
    res = scipy.optimize.fmin_tnc(f, 
            x0,
            None,
            bounds=bounds[0][coords],
            xtol=0.01,
            disp=False)
    for cc, xx in zip(coords, res[0]):
        model[cc] = xx 
    logger.info("pre-trained model:\n%s" % np.array_str(model.x, precision=2))
    return _smcpp.raw_sfs(model, n, 0., _smcpp.T_MAX, False)

def break_long_spans(dataset, rho, length_cutoff):
    # Spans longer than this are broken up
    # FIXME: should depend on rho
    span_cutoff = 1000000
    obs_list = []
    obs_attributes = {}
    for fn, obs in enumerate(dataset):
        long_spans = np.where((obs[:, 0] >= span_cutoff) & (obs[:, 1] == -1) & (obs[:, 3] == 0))[0]
        cob = 0
        logger.debug("Long missing spans: \n%s" % str(obs[long_spans]))
        positions = np.insert(np.cumsum(obs[:, 0]), 0, 0)
        for x in long_spans:
            s = obs[cob:x, 0].sum()
            if s > length_cutoff:
                obs_list.append(np.insert(obs[cob:x], 0, [1, -1, 0, 0], 0))
                sums = obs_list[-1].sum(axis=0)
                s2 = obs_list[-1][:,1][obs_list[-1][:,1]>=0].sum()
                obs_attributes.setdefault(fn, []).append((positions[cob], positions[x], sums[0], 1. * s2 / sums[0], 1. * sums[2] / sums[0]))
            else:
                logger.info("omitting sequence length < %d as less than length cutoff %d" % (s, length_cutoff))
            cob = x + 1
        s = obs[cob:, 0].sum()
        if s > length_cutoff:
            obs_list.append(np.insert(obs[cob:], 0, [1, -1, 0, 0], 0))
            sums = obs_list[-1].sum(axis=0)
            s2 = obs_list[-1][:,1][obs_list[-1][:,1]>=0].sum()
            obs_attributes.setdefault(fn, []).append((positions[cob], positions[-1], sums[0], 1. * s2 / sums[0], 1. * sums[2] / sums[0]))
        else:
            logger.info("omitting sequence length < %d as less than length cutoff %d" % (s, length_cutoff))
    return obs_list, obs_attributes
