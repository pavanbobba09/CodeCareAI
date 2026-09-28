# Eval 2026-09-28-n20-pipeline-extract_v1-openai_gpt-oss-120b

Setup `pipeline`, model `openai/gpt-oss-120b`, prompts `extract_v1+select_v1`.
Code commit `33fa3998b330ac1c0d113ed41678e768457b4950`, code sets ICD10CM-FY2027.
20 notes (0 failed), 35 predicted codes, mean latency 9379 ms.

| Metric | Value | Threshold |
|---|---|---|
| precision | 0.94 ✓ | >= 0.85 |
| recall | 0.85 ✓ | >= 0.8 |
| invented_rate | 0.00 ✓ | == 0.0 |
| invalid_rate | 0.00 ✓ | == 0.0 |
| evidence_ref_invalid_rate | 0.00 ✓ | <= 0.05 |
| unsupported_rate | 0.03 ✓ | <= 0.05 |
| gap_recall | 1.00 ✓ | >= 0.8 |
| em_match | n/a | >= 0.75 |

| Note | Status | Missed | Extra | Invented | Invalid | Unsupported | Gaps expected | Gaps raised |
|---|---|---|---|---|---|---|---|---|
| n001 | completed | - | - | - | - | - | - | - |
| n002 | completed | E11.22 | - | - | - | - | - | - |
| n003 | completed | E11.22 | - | - | - | - | R9 | R9 |
| n004 | completed | E11.65 | E11.9 | - | - | - | - | - |
| n005 | completed | - | - | - | - | - | - | - |
| n006 | completed | - | - | - | - | - | - | - |
| n007 | completed | - | - | - | - | - | - | - |
| n008 | completed | - | - | - | - | - | - | - |
| n009 | completed | - | - | - | - | - | R10 | R10 |
| n010 | completed | - | - | - | - | - | - | - |
| n011 | completed | E11.22 | - | - | - | - | - | - |
| n012 | completed | - | - | - | - | - | R9 | R9 |
| n013 | completed | E11.22 | - | - | - | - | - | - |
| n014 | completed | - | I50.9 | - | - | - | R10 | R10 |
| n015 | completed | R06.02 | - | - | - | - | - | - |
| n016 | completed | - | - | - | - | - | - | - |
| n017 | completed | - | - | - | - | - | - | - |
| n018 | completed | - | - | - | - | - | - | - |
| n019 | completed | - | - | - | - | - | - | - |
| n020 | completed | - | - | - | - | Z79.4 | - | - |
