# Eval 2026-09-27-baseline-openai_gpt-oss-20b

Setup `baseline`, model `openai/gpt-oss-20b`, prompts `baseline_v1`.
10 notes (0 failed), 18 predicted codes, mean latency 4092 ms.

| Metric | Value | Threshold |
|---|---|---|
| precision | 0.39 ✗ | >= 0.85 |
| recall | 0.35 ✗ | >= 0.8 |
| invented_rate | 0.00 ✓ | == 0.0 |
| invalid_rate | 0.17 ✗ | == 0.0 |
| unsupported_rate | 0.00 ✓ | <= 0.05 |
| gap_recall | 0.00 ✗ | >= 0.8 |
| em_match | n/a | >= 0.75 |

| Note | Status | Missed | Extra | Invented | Invalid | Gaps expected | Gaps raised |
|---|---|---|---|---|---|---|---|
| n001 | completed | Z79.84 | - | - | - | - | - |
| n002 | completed | E11.22, N18.32 | E11.9, N18.4 | - | - | - | - |
| n003 | completed | N18.30 | - | - | - | R9 | - |
| n004 | completed | Z79.4 | - | - | - | - | - |
| n005 | completed | - | - | - | - | - | - |
| n006 | completed | I12.9 | I10 | - | - | - | - |
| n007 | completed | I12.0 | I10 | - | - | - | - |
| n008 | completed | I11.0, I50.22 | I10, I50.2 | - | I50.2 | - | - |
| n009 | completed | I11.0 | I10, R23.2 | - | - | R10 | - |
| n010 | completed | I13.0, I50.32, N18.31 | I10, I50.2, N18.3 | - | I50.2, N18.3 | - | - |
