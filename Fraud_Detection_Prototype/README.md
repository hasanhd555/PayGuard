# Part A: fraud detection decisions

The prototype tests whether fraud can be identified with a manageable number of
false alarms. **Random forest is the provisional choice for human-review
flagging at score >= 0.324504778.** It was selected on validation cost before
the final chronological period was evaluated.

The [main README](../README.md#part-a-fraud-detection) explains the methodology,
metric choices, model comparison, operating threshold, error costs and real-time
constraints. The central decisions are:

| Decision | Rationale |
|---|---|
| Chronological train/validation/test split | Test the intended use: learn from earlier transactions and score later ones. |
| Fit preprocessing on training only | Prevent future observations from influencing learned transformations. |
| Balanced class weights without explicit resampling | Give scarce fraud examples more influence while retaining legitimate examples and avoiding synthetic transactions. |
| Logistic regression baseline and random forest alternative | Establish a simple reference, then test whether nonlinear relationships justify added complexity. |
| Average precision for ranking; cost for selection | Ranking quality and the operational consequences of false alarms/missed fraud answer different questions. |
| Validation-selected threshold, frozen before test | Choose an action policy without adapting it to the final evaluation period. |

The forest's validation cost was 1,410 versus logistic regression's 1,425,
under hypothetical FP=5/FN=100 costs. Logistic regression had slightly higher
validation average precision. The 15-unit cost difference is too small to
establish a robust winner.

At the frozen test operating points, forest caught 56 of 74 frauds with 8 false
alarms, versus 55 with 21 false alarms for logistic regression. These results
support a longer, representative validation exercise; they do not establish
production readiness or calibrated fraud probabilities.

- [Setup, dataset and implementation walkthrough](SETUP_AND_DATA.md)
- [Measured tables, plots and sensitivity analysis](results/RESULTS.md)
