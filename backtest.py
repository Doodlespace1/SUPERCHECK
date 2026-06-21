#!/usr/bin/env python3
"""Backtest the SuperCheck Monte Carlo model against realised Chant West
returns (returns_data.csv, 2004-2024).

For each cohort we (1) run a 10,000-iteration Monte Carlo using the fitted
FUND_PARAMS exactly as supercheck.html does, (2) compound the cohort through
the actual annual return series with the same contribution/fee/tax logic but
HISTORICAL SG rates, and (3) report where the actual outcome lands in the
predicted distribution.

Known simplifications (flagged in output):
- The Monte Carlo prediction uses a constant SG rate (the rate in force in
  the cohort's start year); the actual-outcome calculation steps through the
  legislated historical rates.
- Wage growth is a constant 3.5% p.a. in both legs (no actual WPI series).
- All figures are nominal; percentile placement is unaffected by deflation.
"""
import csv
import os
import random
import statistics

# Resolve the data file relative to this script so it runs on any machine.
CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'apra_data', 'returns_data.csv')
ITERATIONS = 10_000
SEED = 42

# Fitted parameters (match supercheck.html CONFIG.FUND_PARAMS)
FUND_PARAMS = {
    'Balanced':    {'mean': 0.067, 'std': 0.094},
    'High Growth': {'mean': 0.080, 'std': 0.117},
}
CONTRIB_TAX = 0.15
WAGE_GROWTH = 0.035
FEE_PCT = 0.8          # representative all-in fee; APRA MySuper admin+investment
                       # ratios ~0.3-0.4% understate indirect costs, and retail
                       # all-in fees run ~1.0-1.5%, so 0.8% is a mid-range proxy.
                       # TODO: sensitivity-test across 0.5-1.2%.

CSV_COL = {'Balanced': 'balanced', 'High Growth': 'high_growth'}


def sg_rate(year):
    """Legislated SG rate applying to calendar/return year `year`."""
    if year < 2013:
        return 0.09
    if year == 2013:
        return 0.0925
    if year <= 2021:
        return 0.095
    return {2022: 0.10, 2023: 0.105, 2024: 0.11}.get(year, 0.115)


def simulate_core(balance, salary, years, sg_const, draw):
    """Shared Monte Carlo loop; `draw()` supplies each year's return."""
    fee = FEE_PCT / 100
    finals = []
    for _ in range(ITERATIONS):
        bal, sal = balance, salary
        for _ in range(years):
            contribution = sal * sg_const * (1 - CONTRIB_TAX)
            bal = max(0.0, bal * (1 + draw() - fee) + contribution)
            sal *= 1 + WAGE_GROWTH
        finals.append(bal)
    finals.sort()
    return finals


def simulate_mc(balance, salary, fund, years, sg_const, rng):
    """Monte Carlo finals using normal i.i.d. annual returns (nominal $)."""
    mean = FUND_PARAMS[fund]['mean']
    std = FUND_PARAMS[fund]['std']
    return simulate_core(balance, salary, years, sg_const,
                         lambda: rng.gauss(mean, std))


def simulate_bootstrap(balance, salary, returns_pool, years, sg_const, rng):
    """Monte Carlo finals resampling actual annual returns with replacement."""
    return simulate_core(balance, salary, years, sg_const,
                         lambda: rng.choice(returns_pool))


def actual_outcome(balance, salary, fund, start_year, returns_by_year):
    """Compound through realised returns with historical SG rates."""
    fee = FEE_PCT / 100
    bal, sal = balance, salary
    for year in range(start_year, 2025):
        r = returns_by_year[year][CSV_COL[fund]]
        contribution = sal * sg_rate(year) * (1 - CONTRIB_TAX)
        bal = bal * (1 + r - fee) + contribution
        sal *= 1 + WAGE_GROWTH
    return bal


def pctile(sorted_finals, p):
    idx = min(len(sorted_finals) - 1, int(p / 100 * len(sorted_finals)))
    return sorted_finals[idx]


def rank_of(sorted_finals, value):
    """Empirical percentile of `value` within the predicted distribution."""
    below = sum(1 for f in sorted_finals if f < value)
    return below / len(sorted_finals) * 100


def main():
    with open(CSV) as f:
        rows = list(csv.DictReader(f))
    returns_by_year = {
        int(r['year']): {c: float(r[c]) / 100 for c in
                         ('high_growth', 'balanced', 'conservative', 'cash')}
        for r in rows
    }

    cohorts = [
        dict(name='A', start=2004, age=40, balance=78_000, salary=75_000,
             fund='Balanced'),
        dict(name='B', start=2008, age=45, balance=120_000, salary=90_000,
             fund='Balanced'),
        dict(name='C', start=2004, age=40, balance=78_000, salary=75_000,
             fund='High Growth'),
    ]

    rng = random.Random(SEED)
    print('=' * 74)
    print(f'BACKTEST — {ITERATIONS:,}-iteration Monte Carlo vs realised '
          f'Chant West returns')
    print(f'Fee {FEE_PCT}% p.a., contributions taxed {CONTRIB_TAX:.0%}, '
          f'wage growth {WAGE_GROWTH:.1%} p.a., nominal dollars')
    print('=' * 74)

    def verdict_for(rank):
        if 25 <= rank <= 75:
            return 'WELL-CALIBRATED (actual within p25-p75)'
        if rank < 25:
            return ('OVERCONFIDENT on the upside (actual below p25 — '
                    'model projected too high)')
        return 'UNDERCONFIDENT (actual above p75 — model projected too low)'

    full_pool = [returns_by_year[y] for y in sorted(returns_by_year)]
    summary = []
    for c in cohorts:
        rng = random.Random(SEED)          # reseed per cohort: isolated + reproducible
        years = 2025 - c['start']          # start year through 2024 inclusive
        sg_const = sg_rate(c['start'])
        pool = [yr[CSV_COL[c['fund']]] for yr in full_pool]
        finals_n = simulate_mc(c['balance'], c['salary'], c['fund'], years,
                               sg_const, rng)
        finals_b = simulate_bootstrap(c['balance'], c['salary'], pool, years,
                                      sg_const, rng)
        actual = actual_outcome(c['balance'], c['salary'], c['fund'],
                                c['start'], returns_by_year)
        rank_n = rank_of(finals_n, actual)
        rank_b = rank_of(finals_b, actual)

        print(f"\nCohort {c['name']}: start {c['start']}, age {c['age']}, "
              f"${c['balance']:,} balance, ${c['salary']:,} salary, "
              f"{c['fund']}, {years} years")
        print(f"  Prediction SG rate: constant {sg_const:.2%} "
              f"(rate in force in {c['start']}) — KNOWN SIMPLIFICATION: the "
              f"actual leg steps through 9% -> 9.25% -> 9.5% -> 10% -> 10.5% "
              f"-> 11%, so the prediction slightly understates late-period "
              f"contributions.")
        print('  Predicted 2024 balance distribution (normal vs bootstrap):')
        print(f"    {'':<6}{'normal':>14}{'bootstrap':>14}")
        for p in (10, 25, 50, 75, 90):
            print(f'    p{p:<5}${pctile(finals_n, p):>12,.0f} '
                  f'${pctile(finals_b, p):>12,.0f}')
        print(f'  Actual outcome (realised returns, historical SG): '
              f'${actual:>12,.0f}')
        print(f'  Actual lands at p{rank_n:.0f} (normal) / p{rank_b:.0f} '
              f'(bootstrap).')
        print(f'  Calibration (normal):    {verdict_for(rank_n)}')
        print(f'  Calibration (bootstrap): {verdict_for(rank_b)}')
        summary.append((c['name'], rank_n, rank_b))

    print('\n' + '=' * 74)
    print('CALIBRATION SUMMARY (in-sample: parameters/pool include the '
          'backtest window)')
    print('=' * 74)
    print(f"  {'Cohort':<8}{'normal':>10}{'bootstrap':>12}")
    for name, rank_n, rank_b in summary:
        print(f'  {name:<8}{"p%.0f" % rank_n:>10}{"p%.0f" % rank_b:>12}')
    print('\nNote: each cohort is a single realised path; three cohorts over '
          'overlapping windows\nis indicative only, not a statistical '
          'validation.')

    # ---------------------------------------------------- holdout validation
    print('\n' + '=' * 74)
    print('HOLDOUT VALIDATION — TRUE OUT-OF-SAMPLE TEST')
    print('Fit/resample on 2004-2014 returns only (11 years); predict a '
          'cohort starting\n2015 (age 50, $165,000 balance, $95,000 salary, '
          'Balanced); compare against the\nactual 2015-2024 outcome. The '
          'model has NOT seen the answer years.')
    print('=' * 74)
    train_years = range(2004, 2015)
    train_pool = [returns_by_year[y]['balanced'] for y in train_years]
    mu = statistics.mean(train_pool)
    sd = statistics.stdev(train_pool)
    print(f'  Training fit (Balanced, 2004-2014): mean {mu:.4f}, '
          f'std {sd:.4f}, n={len(train_pool)}')

    h_balance, h_salary, h_start = 165_000, 95_000, 2015
    h_years = 2025 - h_start                      # 2015..2024 inclusive
    h_sg = sg_rate(h_start)
    rng = random.Random(SEED)                     # isolated, reproducible
    finals_hn = simulate_core(h_balance, h_salary, h_years, h_sg,
                              lambda: rng.gauss(mu, sd))
    finals_hb = simulate_core(h_balance, h_salary, h_years, h_sg,
                              lambda: rng.choice(train_pool))
    h_actual = actual_outcome(h_balance, h_salary, 'Balanced', h_start,
                              returns_by_year)
    hr_n = rank_of(finals_hn, h_actual)
    hr_b = rank_of(finals_hb, h_actual)

    print('  Predicted 2024 balance distribution (normal vs bootstrap, '
          'trained 2004-2014):')
    print(f"    {'':<6}{'normal':>14}{'bootstrap':>14}")
    for p in (10, 25, 50, 75, 90):
        print(f'    p{p:<5}${pctile(finals_hn, p):>12,.0f} '
              f'${pctile(finals_hb, p):>12,.0f}')
    print(f'  Actual 2015-2024 outcome (realised returns, historical SG): '
          f'${h_actual:>12,.0f}')
    print(f'  OUT-OF-SAMPLE RESULT: actual lands at p{hr_n:.0f} (normal) / '
          f'p{hr_b:.0f} (bootstrap).')
    print(f'  Calibration (normal):    {verdict_for(hr_n)}')
    print(f'  Calibration (bootstrap): {verdict_for(hr_b)}')


if __name__ == '__main__':
    main()
