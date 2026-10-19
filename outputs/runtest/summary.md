| Run | Strategy | Correct /3 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| test | S1 direct | 3 | 0 | 6573 | 272 | 2.08 | 6.5 | 0.0016 |
| test | S2 think and vote (k = 5) | 3 | 0 | 33255 | 3008 | 11.04 | 36.1 | 0.0103 |
| test | S3 tools | 3 | 0 | 14180 | 715 | 6.79 | 20.0 | 0.0037 |

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | ✓ | ✓ | ✓ |
| Q-03 | ✓ | ✓ | ✓ |
| Q-09 | ✓ | ✓ | ✓ |
