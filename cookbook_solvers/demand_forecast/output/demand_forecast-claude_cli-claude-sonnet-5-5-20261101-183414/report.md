=== Demand Forecasting (solver=ON / statsmodels UnobservedComponents) ===

Problem:
Use the default 36-month widget sales dataset.

Forecast (6 periods ahead):
| Period | Forecast | Lower 95% | Upper 95% |
|---|---|---|---|
| +1 | 118.8 | 114.4 | 123.3 |
| +2 | 113.8 | 109.2 | 118.5 |
| +3 | 126.8 | 121.9 | 131.7 |
| +4 | 133.2 | 128.1 | 138.3 |
| +5 | 137.2 | 131.9 | 142.5 |
| +6 | 140.8 | 135.3 | 146.3 |

Hold-out RMSE: **2.36** vs naïve baseline 20.16 (✓ beats naïve)

Interpretation:
The forecast points to a clear upward trend: demand climbs from about 119 units in period +1 to about 141 by period +6, roughly 18% growth, after a dip to 114 in period +2. That dip followed by a steady rise (127, 133, 137, 141) suggests a seasonal low just after the forecast starts, with demand then recovering and building. Because the model includes a seasonal component, treat the +2 trough as a recurring pattern rather than noise. For inventory planning, avoid over-ordering for the near-term dip, then ramp replenishment from period +3 onward so stock keeps pace with rising demand, and expect to carry the most inventory around period +5 to +6. Uncertainty is modest: the 95% intervals are narrow (about ±4.5 units at +1, widening to about ±5.5 at +6), and the hold-out RMSE of 2.36 versus a naïve baseline of 20.16 shows the model has been reliable on this dataset. Safety stock can therefore be kept lean, with a small extra buffer in the later periods where the band widens. As always, a 36-month history is short for confirming seasonality, so re-check the forecast as new actuals come in.

LLM calls: 2