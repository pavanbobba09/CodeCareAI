# Eval 2026-09-27-pipeline-openai_gpt-oss-20b

Setup `pipeline`, model `openai/gpt-oss-20b`, prompts `extract_v1+select_v1`.
10 notes (0 failed), 21 predicted codes, mean latency 9552 ms.

| Metric | Value | Threshold |
|---|---|---|
| precision | 0.67 ✗ | >= 0.85 |
| recall | 0.70 ✗ | >= 0.8 |
| invented_rate | 0.00 ✓ | == 0.0 |
| invalid_rate | 0.00 ✓ | == 0.0 |
| unsupported_rate | 0.00 ✓ | <= 0.05 |
| gap_recall | 0.00 ✗ | >= 0.8 |
| em_match | n/a | >= 0.75 |

| Note | Status | Missed | Extra | Invented | Invalid | Gaps expected | Gaps raised |
|---|---|---|---|---|---|---|---|
| n001 | completed | - | - | - | - | - | - |
| n002 | completed | - | - | - | - | - | - |
| n003 | completed | - | - | - | - | R9 | - |
| n004 | completed | E11.65 | E11.9 | - | - | - | - |
| n005 | completed | - | - | - | - | - | - |
| n006 | completed | I12.9 | I10 | - | - | - | - |
| n007 | completed | I12.0 | I10 | - | - | - | - |
| n008 | completed | I11.0 | I10 | - | - | - | - |
| n009 | completed | I11.0 | I10, R60.0 | - | - | R10 | - |
| n010 | completed | I13.0 | I10 | - | - | - | - |
