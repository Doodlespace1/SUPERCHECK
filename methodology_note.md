# SuperCheck Methodology Note

*Prepared 12 June 2026*

## Data sources

Return distributions for the four investment options are fitted to **Chant West SR50/SR25 median annual returns by risk category, 2004–2024** (n = 21 years per category), transcribed from Chant West's published survey data into `returns_data.csv`. Fitted normal parameters (mean, sample standard deviation, as decimals): High Growth 0.080/0.117, Balanced 0.067/0.094, Conservative 0.048/0.052, Cash 0.034/0.018. The 2008 crisis observations (High Growth −26.7%, Balanced −21.8%) are retained deliberately so the fitted distributions reflect real tail risk. Fee defaults come from the **APRA MySuper Bulletin (June 2023)** aggregate fee ratios (admin + investment fees paid over MySuper assets): industry 0.4%, retail 0.3%. These understate all-in member costs because APRA's "fees paid" excludes indirect investment costs netted from unit prices.

## Cross-validation against APRA

The Chant West Balanced series was compared with whole-of-fund Rate of Return figures from the APRA Annual Superannuation Bulletin (Table 9a, Industry and Retail funds, 2004–2019). Mean absolute difference vs APRA Industry: **3.48 percentage points**, above our 3pp tolerance. The divergence is concentrated in four years (2008, 2011, 2012, 2019). The 2011/2012 pair shows a clear **one-year phase shift** (CW 0.9% in 2011 ≈ APRA 0.9% in 2012; CW 9.2% in 2012 ≈ APRA 8.9% in 2011), strongly suggesting the Chant West figures are calendar-year while APRA reports years ended June. APRA's series is also a whole-of-fund aggregate dominated by growth-leaning defaults, so it is not a pure Balanced benchmark. Allowing for these definitional differences, the sources broadly agree on level and shape.

## Backtest design and calibration

Three cohorts were backtested (`backtest.py`, 10,000-iteration Monte Carlo, seed 42, fee 0.8%, 15% contributions tax, 3.5% wage growth, nominal dollars):

| Cohort | Start | Age | Balance | Salary | Option | Actual landed at |
|---|---|---|---|---|---|---|
| A | 2004 | 40 | $78k | $75k | Balanced | p54 — well-calibrated |
| B | 2008 | 45 | $120k | $90k | Balanced | p40 — well-calibrated |
| C | 2004 | 40 | $78k | $75k | High Growth | p54 — well-calibrated |

Actual outcomes compound the realised Chant West returns with **historical SG rates** (9% pre-2013, 9.25%, 9.5% through 2021, then 10%, 10.5%, 11%); predictions use a constant start-year SG rate — a known simplification that slightly depresses predicted contributions late in the window. All three actuals fall inside the p25–p75 band, so the model is **well-calibrated** on these cohorts. Note cohort B starts immediately before the GFC and still lands at p40, indicating the fitted volatility absorbs a worst-case entry point. **Caveat:** these three cohorts are in-sample — the prediction parameters were fitted on the same 2004–2024 window being backtested — so they confirm internal consistency rather than out-of-sample forecasting skill (see the Week 4 holdout test for the latter).

## Known limitations

1. **Normal distribution assumption.** Empirical annual returns are negatively skewed with fat tails (2008 is a >2.9σ event under the fitted Balanced parameters); a normal thins the left tail.
2. **Small sample (n = 21).** Parameter estimates carry meaningful standard error (≈±2pp on the means).
3. **Independence assumption.** Annual returns are simulated i.i.d.; real markets exhibit momentum and mean-reversion (e.g. 2009 following 2008).
4. **Weak validation power.** Each cohort is a single realised path over overlapping windows; three cohorts are indicative, not statistical proof.
5. **Constant wage growth and fees** across the projection horizon.
6. **Drawdown and Age Pension logic is not empirically backtested.** `backtest.py` validates only the accumulation engine against realised 2004–2024 returns. The Week 5–6 depletion-age and Age Pension means-test logic is not backtested against historical data — no such dataset exists. It has only been checked against published pension parameters (asset-test cut-offs) for internal consistency.

**Modelling conventions.** Extra voluntary contributions are indexed to wage growth (3.5% p.a. nominal), the same as employer SG contributions, so their real value is preserved over the horizon. The Monte Carlo is seeded (mulberry32, fixed seed) so identical inputs reproduce identical results — for both the user and QA.

*(See the "Percentile benchmark revision" section at the end for the v1.2 percentile change.)*

**Planned Week 4 improvement:** replace the normal sampler with **bootstrap resampling** of the empirical 2004–2024 returns, specifically because the data shows fat left tails the normal cannot capture; bootstrapping preserves the realised skew and kurtosis without a parametric assumption.

## Week 4: bootstrap resampling

**Why normality was rejected.** The empirical return distributions are left-skewed: under the fitted Balanced parameters (mean 0.067, std 0.094), the 2008 observation of −21.8% is a **>2.9σ event** — roughly a 1-in-500 draw under a normal, yet it sits in a 21-year sample. A normal sampler therefore thins exactly the tail a retirement-risk tool most needs to represent.

**What bootstrap resampling does.** The simulator now draws each simulated year's return uniformly at random, with replacement, from the 21 actual historical returns for the selected option (`CONFIG.HISTORICAL_RETURNS`). The empirical skew and kurtosis — including 2008 — are preserved exactly, with no parametric assumption. All other logic (contributions, wage growth, fees, contributions tax, inflation deflation) is unchanged; the previous sampler is retained as `runMonteCarloNormal` for comparison.

**Calibration comparison (in-sample cohorts, 10,000 iterations).** Normal vs bootstrap: Cohort A p54 → p51, Cohort B p40 → p38, Cohort C p54 → p51 — all well-calibrated under both methods. In the browser (Test A, 39-year horizon, 10×5,000-run averages) bootstrap lowers the 10th percentile ~3% ($380k → $367k) with the median and 90th percentile roughly unchanged, a modest shift because i.i.d. annual draws partially average out over long horizons.

**Holdout (out-of-sample) test.** Fitting/resampling on 2004–2014 only (n = 11) and predicting a 2015-start cohort (age 50, $165k, $95k salary, Balanced) against the realised 2015–2024 outcome: the actual ($428,704) lands at **p68 (normal) / p65 (bootstrap)** — within the p25–p75 band under both methods. This is the only test where the model has not seen the answer years. The actual landing above the median reflects the strong post-2014 bull market relative to the GFC-containing training window.

**Remaining limitation.** Both samplers draw years i.i.d., ignoring year-to-year correlation (e.g. the 2009 rebound following 2008, momentum/mean-reversion generally). A **block bootstrap** — resampling contiguous multi-year blocks rather than single years — would preserve short-range serial structure and is the natural next extension.

## Week 5: retirement drawdown phase

**Design.** Each simulated path now continues past retirement to age 95. During drawdown there are no contributions; the balance keeps earning bootstrapped annual returns net of the user's fee, and an annual withdrawal is deducted at the end of each year. The model records the age at which each path's balance hits zero (or marks it as surviving past 95) and reports the share of 5,000 paths still positive at age 90 — the headline "Money lasts to 90" figure — alongside a histogram of depletion ages.

**Withdrawal assumptions.** The annual withdrawal is the ASFA comfortable budget from the **December 2025 quarter release**: $54,240 (single) or $76,505 (couple), held constant in today's dollars (i.e. indexed to inflation in nominal terms). The ASFA comfortable lump-sum thresholds used elsewhere in the tool were updated to the same release ($630,000 single / $730,000 couple). Withdrawals do not vary with balance or age, and no minimum-drawdown rules or tax in retirement are modelled.

**Key limitation — no Age Pension.** The model excludes the Age Pension entirely. This matters more than any other simplification: ASFA's own comfortable lump sums *assume a part Age Pension* (roughly $25–30k per year for a single homeowner with a modest balance), which is precisely why ASFA says $630,000 supports a comfortable retirement while this pension-free model shows a $477k (real) balance at 67 depleting in the late 70s on the median path, with only ~2% of paths surviving to 90. Survival probabilities reported by the tool are therefore **conservative — materially so for low- and middle-balance retirees**, for whom the pension covers half or more of the comfortable budget. Means-tested Age Pension integration (assets and income tests, homeowner status) is flagged as the priority piece of future work; without it, the survival figure should be read as "money lasts to 90 *unassisted*". *(Addressed in Week 6 below.)*

## Week 6: Age Pension means test

**Design.** Each drawdown year, the model now computes an Age Pension entitlement from the assets test and subtracts it from the year's ASFA budget, so the net withdrawal from super falls as the pension rises: entitlement = max(0, PENSION_MAX − (assessable assets − threshold)/1,000 × $78), capped at the maximum rate. The super balance is the only assessable asset modelled, assessed at its today's-dollar value each year. Because the balance shrinks through drawdown, entitlement is recomputed annually — a retiree typically moves from no pension, to part pension, to full pension as super depletes. The headline "Money lasts to 90" figure is now pension-assisted, with the unassisted figure shown alongside; both legs share identical return draws so the difference isolates the pension effect.

**Parameters** (Services Australia rates from 20 March 2026, updated from the older figures in the build spec): maximum pension $31,223/yr single, $47,070/yr couple combined (including supplements); full-pension asset thresholds for homeowners $321,500 single, $481,500 couple; non-homeowners add $258,000 (a form toggle, defaulting to homeowner); taper $3 per fortnight per $1,000 over the threshold ($78/yr). Pension rates and thresholds are legislatively indexed, so holding them constant in today's dollars is the correct treatment in a real-dollar model.

**Asset-test-only simplification.** The income test is not modelled. For retirees whose income is deemed earnings on financial assets plus drawdowns (not employment), the assets test is usually the binding constraint at the balances where the pension matters — the $78/yr-per-$1,000 taper is equivalent to a 7.8% annual clawback on marginal assets, far steeper than deemed income reduces the pension. The exclusion of deeming and the income test is still a real limitation: for retirees with substantial non-super financial assets or employment income, the income test can bind instead, and this model would overstate their entitlement. Non-super assets (contents, vehicles, investment property) are also excluded from the assessable base, which works in the opposite direction.

**Effect.** The 55-year-old / $210k / Balanced / retire-67 single homeowner test case moves from ~2% unassisted survival-to-90 to **~60% pension-assisted** (the pension alone covers ~58% of the single comfortable budget). A $1.5M-at-retirement case receives no pension until late drawdown and survives in ~99% of paths. The asset-test formula reproduces the published part-pension cut-off ($722,000 single homeowner) exactly.

**Sources.** Services Australia Age Pension rates (20 March 2026); published assets-test thresholds and taper as summarised by SuperGuide ("Age Pension assets test rules, from March 2026") and Equipsuper; ASFA Retirement Standard (December 2025 quarter) for the drawdown budget.

## Week 7: coherence, the pension-gap card, and accessibility

**Coherence labelling.** The fan chart projects super balance only, while the survival figure includes the Age Pension — a low-balance user could see a bleak chart yet a high survival number and reasonably think the tool contradicts itself. Rather than fold the pension into the chart (which would conflate two different things — an accumulation projection and a drawdown safety net), the scopes are now labelled explicitly: a "super only" tag on the fan-chart title, a "super + pension" tag on the survival card, and a one-line caption under the chart stating that the survival figure below includes the pension. Labelling the scopes is more honest than hiding the seam.

**Pension-gap card.** The assisted-minus-unassisted survival gap (e.g. +59pp for the standard case) now has its own card, "What the Age Pension is worth to you". For most low- and middle-balance retirees the pension is worth more than their super, and this surfaces that directly rather than burying it in a sub-line.

**Accessibility measures.** Target users skew 45–65+, so the page was taken to WCAG AA: (1) every interactive element is keyboard-reachable with a visible 3px focus ring — the retirement-type and homeowner toggles previously hid their radios with `display:none`, which removed them from the tab order; they are now visually hidden but focusable, with a `change` listener syncing the card visual on arrow-key selection. (2) All toggles, the "what is this?" buttons, the text-size buttons and the sliders meet a 44px minimum touch target. (3) Every form input has an associated `<label for>`; each result card is a labelled `group` whose `aria-label` is updated with its live value after each calculation, and both charts are `role="img"` with descriptive labels. (4) Colour is never the sole signal: outcome badges carry text, and the fan-chart lines use distinct dash patterns (dotted outer band, solid inner band, thick solid median, long-dash threshold) so they remain distinguishable in greyscale. (5) Contrast was rechecked: the brand amber (#E07B39) failed AA as text on light backgrounds (~3:1), so a darker amber (#B0560F, ~5:1) is now used for the fee-drag figure, the ASFA chart line and label, and a darker tone (#9A4D14) for the amber badge — the brand amber is retained for decorative fills only. (6) A "Text size" toggle bumps the base font from 18px to 21px. Full calculate-to-results compute time, with the Week 5–6 drawdown and means-test additions, measures ~120ms — well under the 500ms target.

## Week 8: Percentile benchmark revision (v1.2, 2026-06-18)
Previous method: log₂-linear heuristic anchored to single ABS median figures — assumed a symmetric log-normal distribution around the median, which the empirical data does not support.

New method: direct lookup against ATO median super balances by age band (ATO Individuals statistics, year ended June 2022, sourced from ASFA "An update on superannuation account balances", September 2024, Table 1). Each anchor is the midpoint of published male and female medians for the band, since ATO does not publish a combined persons median at this granularity.

Anchors: 35→$62k, 40→$88k, 45→$114k, 50→$137k, 55→$157k, 60→$180k, 65→$199k.

Remaining limitation: SIH/ATO data reflects 2021–22 balances; super balances have grown since, so benchmarks slightly understate the current distribution and may modestly overstate a user's relative standing. The log₂-linear mapping around the single anchor is retained — this is still a heuristic estimate, not a true decile interpolation, since ATO does not publish decile breakpoints by age.

Effect: older users read as further ahead (65yo/$320k: 50th → 67th percentile); younger users read as slightly behind (35yo/$45k: 50th → 38th percentile).
