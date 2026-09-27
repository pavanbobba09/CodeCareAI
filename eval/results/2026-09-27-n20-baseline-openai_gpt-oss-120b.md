# Eval 2026-09-27-n20-baseline-openai_gpt-oss-120b

Setup `baseline`, model `openai/gpt-oss-120b`, prompts `baseline_v1`.
20 notes (0 failed), 34 predicted codes, mean latency 4008 ms.

| Metric | Value | Threshold |
|---|---|---|
| precision | 0.56 ✗ | >= 0.85 |
| recall | 0.49 ✗ | >= 0.8 |
| invented_rate | 0.03 ✗ | == 0.0 |
| invalid_rate | 0.12 ✗ | == 0.0 |
| unsupported_rate | 0.00 ✓ | <= 0.05 |
| gap_recall | 0.00 ✗ | >= 0.8 |
| em_match | n/a | >= 0.75 |

| Note | Status | Missed | Extra | Invented | Invalid | Gaps expected | Gaps raised |
|---|---|---|---|---|---|---|---|
| n001 | completed | Z79.84 | - | - | - | - | - |
| n002 | completed | N18.32 | N18.3 | - | N18.3 | - | - |
| n003 | completed | N18.30 | N18.3 | - | N18.3 | R9 | - |
| n004 | completed | Z79.4 | - | - | - | - | - |
| n005 | completed | - | - | - | - | - | - |
| n006 | completed | I12.9 | I10 | - | - | - | - |
| n007 | completed | I12.0 | I10 | - | - | - | - |
| n008 | completed | I11.0 | I10 | - | - | - | - |
| n009 | completed | I11.0 | I10, R60.0 | - | - | R10 | - |
| n010 | completed | I13.0, I50.32 | I10, I50.31 | - | - | - | - |
| n011 | completed | E11.22, I13.0, N18.32 | E11.23, I10 | E11.23 | E11.23 | - | - |
| n012 | completed | - | - | - | - | R9 | - |
| n013 | completed | E11.22, I12.9, N18.32 | E11.9, I10, N18.3 | - | N18.3 | - | - |
| n014 | completed | I50.20 | I50.22 | - | - | R10 | - |
| n015 | completed | - | - | - | - | - | - |
| n016 | completed | - | - | - | - | - | - |
| n017 | completed | - | - | - | - | - | - |
| n018 | completed | Z79.84 | - | - | - | - | - |
| n019 | completed | - | - | - | - | - | - |
| n020 | completed | Z79.4, Z79.84 | - | - | - | - | - |
