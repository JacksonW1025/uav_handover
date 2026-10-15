# P4 table: data/p4-20261016-dev-05

Measured takeover (p3_sequence: second C→N; p2_c_to_n: C→N; baselines: re-capture). Mean [95% t interval].

| group | n | speed at takeover m/s | accel m/s² | motor step | motor RMS vs baseline | max alt. loss m | max tilt ° | recovery s | GRU dist @0 / 0.1 / 0.25 s |
|---|---:|---|---|---|---|---|---|---|---|
| D2:N0 | 2 | -0.000 [-0.062, 0.061] | -0.01 [-0.38, 0.36] | 0.203 [-0.052, 0.458] | 0.0718 [0.0110, 0.1326] | 0.042 [-0.021, 0.104] | 1.5 [-0.7, 3.8] | 1.68 [-8.66, 12.02] | 0.901 / 0.400 / 0.211 |
| M3:N0 | 1 | 1.095 | -0.02 | 0.544 | — | 0.180 | 34.8 | 3.23 |  |
| R:B | 1 | -0.015 | -0.03 | 0.006 | 0.0000 | 0.015 | 0.6 | 0.00 | 0.000 / 0.000 / 0.000 |

Elimination (N0 − Nx)/(N0 − baseline), 95% bootstrap interval; total cost N0 − baseline.

| unit:treatment | metric | total cost | ratio | 95% interval | remainder (capture) |
|---|---|---:|---:|---|---:|

First C→N (always N0), pooled n=4: motor step 0.221 [0.210, 0.232], altitude loss 0.035 [0.027, 0.043] m, recovery 1.23 [0.10, 2.36] s.
