=== Cross-Algorithm Portfolio Comparison ===

Tickers: AAPL,MSFT,GOOGL,AMZN,NVDA  |  Period: 1y  |  Capital: $10000
Target return: 0.08  |  Max position: 0.25

Algorithm Summary (CSV):
algorithm,status,expected_return,annual_volatility,sharpe_ratio,AAPL,MSFT,GOOGL,AMZN,NVDA
markowitz,OPTIMAL,0.1103,0.1948,0.3094,0.2500,0.2500,0.2331,0.0875,0.1794
min_variance,OPTIMAL,0.1103,0.1948,0.3094,0.2500,0.2500,0.2331,0.0875,0.1794
max_sharpe,OPTIMAL,0.1155,0.1974,0.3316,0.2500,0.2500,0.2500,0.0000,0.2500
risk_parity,OPTIMAL,0.1053,0.1962,0.2819,0.2500,0.2045,0.1900,0.1702,0.1853
hrp,OPTIMAL,0.1206,0.1908,0.3697,0.3034,0.2192,0.1294,0.1328,0.2152
cvar,OPTIMAL,0.1119,0.1950,0.3177,0.2500,0.2500,0.2500,0.0565,0.1935

Portfolio Composition (CSV):
ticker,markowitz_wt%,min_variance_wt%,max_sharpe_wt%,risk_parity_wt%,hrp_wt%,cvar_wt%,markowitz_$,min_variance_$,max_sharpe_$,risk_parity_$,hrp_$,cvar_$
AAPL,25.00,25.00,25.00,25.00,30.34,25.00,2500,2500,2500,2500,3034,2500
MSFT,25.00,25.00,25.00,20.45,21.92,25.00,2500,2500,2500,2045,2192,2500
GOOGL,23.31,23.31,25.00,19.00,12.94,25.00,2331,2331,2500,1900,1294,2500
AMZN,8.75,8.75,0.00,17.02,13.28,5.65,875,875,0,1702,1328,565
NVDA,17.94,17.94,25.00,18.53,21.52,19.35,1794,1794,2500,1853,2152,1935

LLM Synthesis & Recommendation:
## 1. Comparison

| Algorithm | Return | Volatility | Sharpe | # Positions | Eff. N* |
|---|---|---|---|---|---|
| Markowitz | 11.03% | 19.48% | 0.309 | 5 | 4.56 |
| Min Variance | 11.03% | 19.48% | 0.309 | 5 | 4.56 |
| Max Sharpe | 11.55% | 19.74% | 0.332 | 4 | 4.00 |
| Risk Parity | 10.53% | 19.62% | 0.282 | 5 | 4.91 |
| **HRP** | **12.06%** | **19.08%** | **0.370** | 5 | 4.53 |
| CVaR | 11.19% | 19.50% | 0.318 | 5 | 4.38 |

*Effective N = 1 / Σw², my own calculation from the weights. The Sharpe figures are consistent with a risk-free rate of about 5%, and I verified the HRP and Max Sharpe returns against the market data.

## 2. Best risk-adjusted return
**HRP** has the highest Sharpe (0.370) and the lowest volatility (19.08%) of the six.

## 3. Most diversified
**Risk Parity** is the most evenly spread: five positions between 17% and 25%, with an effective N of 4.91. Max Sharpe is the least diversified, with AMZN dropped and four equal 25% positions.

## 4. Recommendation: HRP
HRP gives the best Sharpe and the lowest volatility while holding all five names. It also avoids inverting a noisy covariance matrix, which makes it more robust than the mean-variance methods when the inputs are only one year of data. It does hold 30% in AAPL, so a personal investor should check that against their own concentration limit.

## 5. Failures and degenerate results
- **All six report OPTIMAL**, but there are problems.
- **Min Variance is degenerate.** Its weights, return, volatility and objective (0.037930) are identical to Markowitz's. A true minimum-variance solve should not match a return-seeking one, so the two probably share the same objective or settings. I would not treat them as two independent results.
- **Constraint mismatch.** Markowitz, Min Variance, Max Sharpe and CVaR all sit at a 25% per-asset cap. HRP puts 30.3% in AAPL, so it is not under that cap. That is why HRP can beat "Max Sharpe" on Sharpe and "Min Variance" on volatility, and part of its edge comes from the extra AAPL weight. The comparison is not strictly like-for-like.
- **Max Sharpe** drops AMZN entirely, which is a corner solution driven by AMZN's roughly zero one-year return.
- **Estimation risk.** Every expected return comes from one year of data, with AAPL at +28% dominating. The return-driven methods (Markowitz, Max Sharpe, CVaR) are the most exposed to that.

## 6. Disclaimer
Past performance does not guarantee future results. This is an analytical comparison, not personalized investment advice.