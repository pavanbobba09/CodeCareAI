# Eval 2026-09-27-baseline-openai_gpt-oss-120b

Setup `baseline`, model `openai/gpt-oss-120b`, prompts `baseline_v1`.
10 notes (0 failed), 19 predicted codes, mean latency 3788 ms.

| Metric | Value | Threshold |
|---|---|---|
| precision | 0.53 ✗ | >= 0.85 |
| recall | 0.50 ✗ | >= 0.8 |
| invented_rate | 0.00 ✓ | == 0.0 |
| invalid_rate | 0.11 ✗ | == 0.0 |
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
