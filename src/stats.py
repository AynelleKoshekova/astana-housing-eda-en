"""Statistical tools for the EDA, built on numpy/scipy (no statsmodels).

- bootstrap_median_diff — difference in medians of two groups with a bootstrap CI
- pairwise_mannwhitney  — pairwise Mann–Whitney tests with Holm correction
- ols_hc3               — OLS with heteroskedasticity-robust (HC3) standard errors
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats


def bootstrap_median_diff(a, b, n_boot: int = 5000, ci: float = 0.95, seed: int = 42) -> dict:
    """median(a) − median(b) with a percentile bootstrap interval."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    boots = np.array([
        np.median(rng.choice(a, a.size)) - np.median(rng.choice(b, b.size))
        for _ in range(n_boot)
    ])
    lo, hi = np.quantile(boots, [(1 - ci) / 2, (1 + ci) / 2])
    diff = np.median(a) - np.median(b)
    return {"diff": diff, "ci_low": lo, "ci_high": hi, "rel_diff": diff / np.median(b)}


def holm(pvals) -> np.ndarray:
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (p.size - rank) * p[i])
        adj[i] = min(running, 1.0)
    return adj


def pairwise_mannwhitney(df: pd.DataFrame, value: str, group: str) -> pd.DataFrame:
    groups = {k: v[value].dropna().to_numpy() for k, v in df.groupby(group, observed=True)}
    rows = []
    for g1, g2 in combinations(sorted(groups), 2):
        u, p = stats.mannwhitneyu(groups[g1], groups[g2], alternative="two-sided")
        # rank-biserial correlation: effect size in [-1, 1]
        r = 1 - 2 * u / (groups[g1].size * groups[g2].size)
        rows.append({"group_1": g1, "group_2": g2,
                     "median_1": np.median(groups[g1]), "median_2": np.median(groups[g2]),
                     "effect_r": -r, "p": p})
    out = pd.DataFrame(rows)
    out["p_holm"] = holm(out["p"])
    return out.sort_values("p_holm").reset_index(drop=True)


def kruskal_by(df: pd.DataFrame, value: str, group: str) -> dict:
    samples = [g[value].dropna().to_numpy() for _, g in df.groupby(group, observed=True)]
    h, p = stats.kruskal(*samples)
    n, k = sum(s.size for s in samples), len(samples)
    eps2 = (h - k + 1) / (n - k)  # epsilon²: share of rank variance "explained" by the grouping
    return {"H": h, "p": p, "epsilon_sq": eps2, "k": k, "n": n}


def ols_hc3(y: pd.Series, X: pd.DataFrame) -> pd.DataFrame:
    """OLS: β = (XᵀX)⁻¹Xᵀy with HC3 covariance (robust to heteroskedasticity).

    X must already contain the constant and dummy variables.
    """
    Xm = X.to_numpy(float)
    yv = y.to_numpy(float)
    n, k = Xm.shape
    XtX_inv = np.linalg.pinv(Xm.T @ Xm)
    beta = XtX_inv @ Xm.T @ yv
    resid = yv - Xm @ beta
    h = np.einsum("ij,jk,ik->i", Xm, XtX_inv, Xm)          # leverage
    omega = (resid / (1 - h)) ** 2
    cov = XtX_inv @ (Xm.T * omega) @ Xm @ XtX_inv
    se = np.sqrt(np.diag(cov))
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), df=n - k)
    crit = stats.t.ppf(0.975, df=n - k)
    r2 = 1 - resid.var() / yv.var()
    out = pd.DataFrame({"coef": beta, "se_hc3": se, "t": t, "p": p,
                        "ci_low": beta - crit * se, "ci_high": beta + crit * se}, index=X.columns)
    out.attrs.update(r2=r2, adj_r2=1 - (1 - r2) * (n - 1) / (n - k), n=n, k=k)
    return out


def design_matrix(df: pd.DataFrame, numeric: list[str], categorical: dict[str, str]) -> pd.DataFrame:
    """Constant + numeric columns + dummies. categorical = {column: base category}."""
    parts = [pd.Series(1.0, index=df.index, name="const"), df[numeric].astype(float)]
    for col, base in categorical.items():
        d = pd.get_dummies(df[col], prefix=col, prefix_sep=": ", dtype=float)
        parts.append(d.drop(columns=f"{col}: {base}"))
    return pd.concat(parts, axis=1)
