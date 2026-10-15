# P4 table: data/p4-20261016-dev-04

Measured takeover (p3_sequence: second C→N; p2_c_to_n: C→N; baselines: re-capture). Mean [95% t interval].

| group | n | speed at takeover m/s | accel m/s² | motor step | motor RMS vs baseline | max alt. loss m | max tilt ° | recovery s | GRU dist @0 / 0.1 / 0.25 s |
|---|---:|---|---|---|---|---|---|---|---|
| M1a:B | 1 | 1.015 | -0.34 | 0.468 | — | 0.115 | 31.0 | 5.94 |  |
| M1a:N0 | 1 | 1.165 | 0.03 | 0.558 | — | 0.211 | 37.5 | 5.88 |  |
| M1b:B | 1 | 1.058 | 0.10 | 0.474 | — | 0.118 | 31.9 | 2.74 |  |
| M2:B | 1 | 0.331 | -1.31 | 0.186 | 0.0000 | 0.018 | 8.9 | 1.66 | 0.000 / 0.000 / 0.000 |
| M2:N0 | 1 | 0.406 | -1.20 | 0.298 | 0.0667 | 0.049 | 12.2 | 3.59 | 1.058 / 0.372 / 0.240 |
| M2a:B | 1 | 0.339 | -1.32 | 0.194 | — | 0.022 | 9.0 | 2.02 |  |
| M2b:B | 1 | 0.263 | -1.47 | 0.147 | — | 0.042 | 9.7 | 1.52 |  |

Elimination (N0 − Nx)/(N0 − baseline), 95% bootstrap interval; total cost N0 − baseline.

| unit:treatment | metric | total cost | ratio | 95% interval | remainder (capture) |
|---|---|---:|---:|---|---:|
