"""P8 的两种在线基线（在 Thor 上逐轮决定下一条用例），2026-10-21。只依赖 numpy、scipy。
用法：m = Fuzz(sut, seed, fits) 或 BO(sut, seed, fits)；循环 c = m.propose(history)，飞完把 (c, score, fail) 追加到 history，
  score = 最大倾角（°），fail 按主判据（P6 冻结的飞行失败判据）。高度损失 > 1 m 的任务判据只并列报告，不作反馈，和我们的方法一样。
fits(c) → bool：用例能否放进安全预算（Thor 的 gap_spec）；放不下的候选在提议阶段就被过滤，不消耗预算。
两者都以真实 score 为反馈：Fuzz 是变异式模糊测试（SaFUZZ / 灰盒 fuzz 的思路）；BO 是贝叶斯优化，GP 拟合 STL 鲁棒度 ρ = 45 − score，EI 选点（S-TaLiRo 一类证伪的思路）。"""
import numpy as np
from scipy.stats import norm as _N
import p8_space as S
N_INIT = 8

class _Base:
    def __init__(self, sut, seed, fits): self.sut, self.fits = sut, fits; self.rng = np.random.default_rng(seed)
    def _sample_fit(self, gen, tries=500):
        for _ in range(tries):
            c = gen()
            if self.fits(c): return c
        raise RuntimeError("找不到能放进安全预算的候选")

class Fuzz(_Base):
    def propose(self, hist):
        if len(hist) < N_INIT: return self._sample_fit(lambda: S.sample(self.rng, self.sut))
        top = sorted(hist, key=lambda h: -h[1])[:5]
        return self._sample_fit(lambda: S.mutate(self.rng, top[int(self.rng.integers(len(top)))][0], self.sut))

class BO(_Base):
    def propose(self, hist):
        if len(hist) < N_INIT: return self._sample_fit(lambda: S.sample(self.rng, self.sut))
        X = np.array([S.encode(h[0], self.sut) for h in hist]); y = np.array([45.0 - h[1] for h in hist])
        best = min(hist, key=lambda h: 45.0 - h[1])[0]
        cand = [c for c in [S.sample(self.rng, self.sut) for _ in range(1200)] + [S.mutate(self.rng, best, self.sut) for _ in range(400)] if self.fits(c)]
        Q = np.array([S.encode(c, self.sut) for c in cand])
        mu0, sd0 = y.mean(), y.std() + 1e-9; yn = (y - mu0) / sd0; ls = 0.35
        k = lambda A, B: np.exp(-0.5 * ((A[:, None, :] - B[None, :, :]) ** 2).sum(-1) / ls ** 2)
        L = np.linalg.cholesky(k(X, X) + 1e-4 * np.eye(len(X))); al = np.linalg.solve(L.T, np.linalg.solve(L, yn))
        Ks = k(Q, X); mu = Ks @ al; v = np.linalg.solve(L, Ks.T); sd = np.sqrt(np.maximum(1 - (v ** 2).sum(0), 1e-9))
        b = yn.min(); z = (b - mu) / sd; ei = (b - mu) * _N.cdf(z) + sd * _N.pdf(z)
        return cand[int(np.argmax(ei))]
