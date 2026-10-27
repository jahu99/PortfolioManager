"""Tests for backtest_pit. Run from the repo root:

    python -m unittest tests.test_pit_backtest -v
"""
import unittest

import numpy as np
import pandas as pd

from backtest_pit.data import PricePanel
from backtest_pit.evaluate import (block_bootstrap_ci, eligibility, evaluate_factor, forward_returns,
                                   month_end_positions)
from backtest_pit.factors import FACTORS, momentum, rsi_wilder, technical_score
from backtest_pit.portfolio import simulate_top_n, summarize_portfolio


def make_panel(n_days=700, n_tickers=200, seed=0, drift_scale=0.0, vol=0.02, autocorr=0.0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n_days)
    cols = [f"T{i:03d}" for i in range(n_tickers)]
    mu = drift_scale * rng.standard_normal(n_tickers)
    noise = vol * rng.standard_normal((n_days, n_tickers))
    rets = noise.copy()
    if autocorr:
        for t in range(1, n_days):
            rets[t] = autocorr * rets[t - 1] + noise[t]
    rets += mu[None, :]
    px = 50.0 * np.exp(np.cumsum(rets, axis=0))
    volume = rng.lognormal(13, 0.5, size=(n_days, n_tickers))
    close = pd.DataFrame(px, idx, cols)
    return PricePanel(close, close.copy(), pd.DataFrame(volume, idx, cols))


def all_eligible(panel):
    return pd.DataFrame(True, index=panel.index, columns=panel.close.columns)


class TestNoLookAhead(unittest.TestCase):
    def test_future_data_cannot_change_past_factor_values(self):
        cut = 450
        a = make_panel(seed=1)
        rng = np.random.default_rng(99)
        b_close, b_adj, b_vol = a.close.copy(), a.adj_close.copy(), a.volume.copy()
        shape = b_close.iloc[cut + 1:].shape
        b_close.iloc[cut + 1:] = rng.uniform(1, 500, shape)
        b_adj.iloc[cut + 1:] = rng.uniform(1, 500, shape)
        b_vol.iloc[cut + 1:] = rng.uniform(1, 1e7, shape)
        b = PricePanel(b_close, b_adj, b_vol)
        for name, fn in FACTORS.items():
            fa, fb = fn(a, 0).iloc[: cut + 1], fn(b, 0).iloc[: cut + 1]
            np.testing.assert_allclose(fa.to_numpy(), fb.to_numpy(), equal_nan=True, err_msg=name)


class TestTechnicalScoreParity(unittest.TestCase):
    @staticmethod
    def _ref_rsi(close, window=14):
        """Scalar re-implementation with the `ta` library's semantics (NaN diff -> 0 at row 0)."""
        n = len(close)
        diff = np.diff(close, prepend=np.nan)
        up = np.where(diff > 0, diff, 0.0)
        dn = np.where(diff < 0, -diff, 0.0)
        a = 1.0 / window
        eu, ed = np.empty(n), np.empty(n)
        eu[0], ed[0] = up[0], dn[0]
        for i in range(1, n):
            eu[i] = a * up[i] + (1 - a) * eu[i - 1]
            ed[i] = a * dn[i] + (1 - a) * ed[i - 1]
        with np.errstate(divide="ignore", invalid="ignore"):
            rsi = np.where(ed == 0, 100.0, 100.0 - 100.0 / (1.0 + eu / ed))
        rsi[: window - 1] = np.nan
        return rsi

    @staticmethod
    def _ref_score(close, volume, rsi, t):
        c = close[t]
        sma50, sma200 = close[t - 49: t + 1].mean(), close[t - 199: t + 1].mean()
        ret3m = c / close[t - 63] - 1.0
        vavg = volume[t - 19: t + 1].mean()
        trend = (25 if c > sma200 else 0) + (15 if c > sma50 else 0)
        mom = (15 if 50 <= rsi[t] <= 70 else 0) + (15 if ret3m > 0.20 else 8 if ret3m > 0 else 0)
        ratio = volume[t] / vavg if vavg > 0 else 0
        vol = 20 if ratio > 1.5 else 10 if ratio > 1.2 else 0
        risk = 10 if c > sma200 else 2
        return min(trend + mom + vol + risk, 100)

    def test_matches_scalar_reference_of_live_rules(self):
        p = make_panel(n_days=600, n_tickers=12, seed=3, drift_scale=0.0008)
        score = technical_score(p.close, p.volume)
        checked = 0
        for col in p.close.columns:
            close, vol = p.close[col].to_numpy(), p.volume[col].to_numpy()
            rsi = self._ref_rsi(close)
            for t in range(230, 600, 11):
                self.assertEqual(score[col].iloc[t], self._ref_score(close, vol, rsi, t), msg=f"{col} t={t}")
                checked += 1
        self.assertGreater(checked, 300)

    def test_nan_until_enough_history(self):
        p = make_panel(n_days=300, n_tickers=3, seed=4)
        s = technical_score(p.close, p.volume)
        self.assertTrue(s.iloc[:199].isna().all().all())
        self.assertTrue(s.iloc[199:].notna().all().all())

    def test_matches_live_scorer_when_available(self):
        try:
            from analysis.indicators import add_indicators
            from analysis.scorer import score_stock
        except Exception as exc:  # `ta` missing, or live modules not importable here
            self.skipTest(f"live scorer not importable: {exc}")
        p = make_panel(n_days=400, n_tickers=6, seed=5, drift_scale=0.0008)
        score = technical_score(p.close, p.volume)
        for col in p.close.columns:
            for t in (260, 320, 399):
                df = pd.DataFrame({"Open": p.close[col], "High": p.close[col], "Low": p.close[col],
                                   "Close": p.close[col], "Volume": p.volume[col]}).iloc[: t + 1]
                live = score_stock(add_indicators(df))["Technical Score"]
                self.assertEqual(score[col].iloc[t], live, msg=f"{col} t={t}")


class TestForwardReturns(unittest.TestCase):
    def test_lag_and_horizon_arithmetic(self):
        adj = pd.DataFrame({"A": np.arange(100.0, 160.0)}, index=pd.bdate_range("2021-01-01", periods=60))
        pos = np.array([10, 20])
        fr = forward_returns(adj, pos, horizon=5, lag=1)
        self.assertAlmostEqual(fr["A"].iloc[0], 116.0 / 111.0 - 1.0)
        fr0 = forward_returns(adj, pos, horizon=5, lag=0)
        self.assertAlmostEqual(fr0["A"].iloc[0], 115.0 / 110.0 - 1.0)

    def test_windows_past_the_end_are_dropped(self):
        adj = pd.DataFrame({"A": np.arange(100.0, 130.0)}, index=pd.bdate_range("2021-01-01", periods=30))
        fr = forward_returns(adj, np.array([10, 27]), horizon=5, lag=1)
        self.assertEqual(len(fr), 1)

    def test_delisted_name_exits_at_last_price_not_dropped(self):
        a = np.arange(100.0, 160.0)
        a[30:] = np.nan  # stops trading
        adj = pd.DataFrame({"A": a}, index=pd.bdate_range("2021-01-01", periods=60))
        fr = forward_returns(adj, np.array([10]), horizon=40, lag=1)
        self.assertAlmostEqual(fr["A"].iloc[0], 129.0 / 111.0 - 1.0)


class TestBootstrap(unittest.TestCase):
    def test_ci_coverage_is_sane_for_iid_noise(self):
        hits = 0
        trials = 300
        rng = np.random.default_rng(0)
        for i in range(trials):
            lo, hi = block_bootstrap_ci(rng.standard_normal(20), 1, 600, (0.05,), seed=i)[0]
            hits += lo <= 0 <= hi
        self.assertGreater(hits / trials, 0.85)

    def test_ci_excludes_zero_for_clear_effect(self):
        lo, hi = block_bootstrap_ci(np.full(30, 0.1) + np.random.default_rng(1).normal(0, 0.02, 30), 1)[0]
        self.assertGreater(lo, 0)


class TestEvaluation(unittest.TestCase):
    def _eval(self, panel, factor, horizon=21, lag=1, n_boot=1000, n_tests=1):
        return evaluate_factor("f", factor, panel.adj_close, all_eligible(panel), month_end_positions(panel.index),
                               horizon, lag, n_tests, min_names=50, n_boot=n_boot, seed=0)

    def test_detects_a_real_signal(self):
        p = make_panel(n_days=900, n_tickers=250, seed=11, drift_scale=0.0012)
        row, _ = self._eval(p, momentum(p.adj_close, 252, 21))
        self.assertGreater(row["mean_ic"], 0.05)
        self.assertGreater(row["ic_lo"], 0.0)
        self.assertGreater(row["top_vs_universe"], 0.0)
        self.assertGreater(row["tvu_lo"], 0.0)

    def test_does_not_find_signal_in_noise_false_positive_rate(self):
        rejections, trials = 0, 25
        for seed in range(trials):
            p = make_panel(n_days=600, n_tickers=150, seed=100 + seed)
            row, _ = self._eval(p, momentum(p.adj_close, 252, 21), n_boot=500)
            rejections += (row["ic_lo"] > 0) or (row["ic_hi"] < 0)
        self.assertLessEqual(rejections / trials, 0.25)

    def test_a_leaky_factor_is_caught_by_the_pipeline(self):
        p = make_panel(n_days=500, n_tickers=150, seed=7)
        pos = month_end_positions(p.index)
        leak = forward_returns(p.adj_close, pos, 21, 1).reindex(p.index)  # the answer itself
        row, _ = self._eval(p, leak)
        self.assertGreater(row["mean_ic"], 0.95)

    def test_execution_lag_removes_the_one_day_edge(self):
        p = make_panel(n_days=900, n_tickers=400, seed=21, autocorr=0.3)
        today = p.adj_close / p.adj_close.shift(1) - 1.0  # known at the close of t
        ic0, _ = self._eval(p, today, horizon=1, lag=0)
        ic1, _ = self._eval(p, today, horizon=1, lag=1)
        self.assertGreater(ic0["mean_ic"], ic1["mean_ic"] + 0.1)


class TestPortfolio(unittest.TestCase):
    def _flat_panel(self, n_days=300, n_tickers=60):
        idx = pd.bdate_range("2020-01-01", periods=n_days)
        cols = [f"T{i:02d}" for i in range(n_tickers)]
        one = pd.DataFrame(100.0, idx, cols)
        return PricePanel(one, one.copy(), pd.DataFrame(1e6, idx, cols))

    def test_costs_charge_only_on_traded_notional(self):
        p = self._flat_panel()
        rng = np.random.default_rng(0)
        static = pd.DataFrame(np.tile(rng.permutation(60), (300, 1)).astype(float), p.index, p.close.columns)
        sim = simulate_top_n(p, static, all_eligible(p), month_end_positions(p.index), top_n=10, cost_bps=20)
        self.assertAlmostEqual(sim["turnover"].iloc[0], 1.0)
        self.assertAlmostEqual(sim["net"].iloc[0], -0.002)
        self.assertTrue((sim["turnover"].iloc[1:].abs() < 1e-12).all())
        self.assertTrue((sim["net"].iloc[1:].abs() < 1e-12).all())

    def test_hysteresis_lowers_turnover(self):
        p = make_panel(n_days=500, n_tickers=120, seed=2)
        rng = np.random.default_rng(1)
        churn = pd.DataFrame(rng.standard_normal(p.close.shape), p.index, p.close.columns)
        pos = month_end_positions(p.index)
        el = all_eligible(p)
        plain = simulate_top_n(p, churn, el, pos, top_n=10, exit_rank=10)
        sticky = simulate_top_n(p, churn, el, pos, top_n=10, exit_rank=30)
        self.assertLess(sticky["turnover"].mean(), plain["turnover"].mean())

    def test_summary_reports_costs_and_periods(self):
        p = make_panel(n_days=500, n_tickers=120, seed=2)
        sim = simulate_top_n(p, technical_score(p.close, p.volume), eligibility(p, 0, 0), month_end_positions(p.index),
                             top_n=10)
        s = summarize_portfolio(sim, n_boot=200)
        self.assertEqual(s["n_periods"], len(sim))
        self.assertGreaterEqual(s["total_cost"], 0.0019)


class TestReport(unittest.TestCase):
    def test_intervals_are_withheld_when_there_are_too_few_independent_periods(self):
        from backtest_pit.run import build_report
        row = dict(factor="f", horizon_days=63, n_dates=11, indep_periods=3.7, mean_names=3000, mean_tied_at_top=5,
                   mean_ic=0.065, ic_lo=0.03, ic_hi=0.14, ic_adj_lo=0.02, ic_adj_hi=0.15, ic_hit_rate=0.7,
                   top_vs_universe=0.02, tvu_lo=0.0, tvu_hi=0.04, tvu_adj_lo=-0.01, tvu_adj_hi=0.05,
                   top_vs_bottom=0.05)
        summary = pd.DataFrame([row, {**row, "horizon_days": 21, "indep_periods": 20.0}])
        meta = dict(n_tickers=1, n_dates=1, start="a", end="b", n_signal_dates=1, lag=1, min_price=5,
                    min_dollar_volume=1e6, top_n=20, exit_rank=20, cost_bps=20)
        text = build_report(meta, summary, {}, 2, min_indep=12)
        self.assertEqual(text.count("[too few periods]"), 2)  # IC cell and top-universe cell of the 63d row only


if __name__ == "__main__":
    unittest.main()
