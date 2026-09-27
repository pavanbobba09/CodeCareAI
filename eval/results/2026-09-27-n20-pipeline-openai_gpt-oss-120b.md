# Eval 2026-09-27-n20-pipeline-openai_gpt-oss-120b

Setup `pipeline`, model `openai/gpt-oss-120b`, prompts `extract_v1+select_v1`.
20 notes (0 failed), 41 predicted codes, mean latency 10705 ms.

| Metric | Value | Threshold |
|---|---|---|
| precision | 0.78 ✗ | >= 0.85 |
| recall | 0.82 ✓ | >= 0.8 |
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
| n004 | completed | - | - | - | - | - | - |
| n005 | completed | - | - | - | - | - | - |
| n006 | completed | I12.9 | I10 | - | - | - | - |
| n007 | completed | - | I10 | - | - | - | - |
| n008 | completed | I11.0 | I10 | - | - | - | - |
| n009 | completed | I11.0 | I10, R60.9 | - | - | R10 | - |
| n010 | completed | I13.0 | I10 | - | - | - | - |
| n011 | completed | I13.0 | I10 | - | - | - | - |
| n012 | completed | - | - | - | - | R9 | - |
| n013 | completed | I12.9 | I10 | - | - | - | - |
| n014 | completed | - | I50.9 | - | - | R10 | - |
| n015 | completed | R06.02 | - | - | - | - | - |
| n016 | completed | - | - | - | - | - | - |
| n017 | completed | - | - | - | - | - | - |
| n018 | completed | - | - | - | - | - | - |
| n019 | completed | - | - | - | - | - | - |
| n020 | completed | - | - | - | - | - | - |
