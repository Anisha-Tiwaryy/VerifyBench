# VerifyBench: Benchmarking Identity Verification APIs

A case study on how I would benchmark identity verification APIs, explain why verifications fail, and plan OCR training data sourcing. The full write-up with charts is in `CASE_STUDY.pdf`.

**Live results page:** https://anisha-tiwaryy.github.io/VerifyBench/

**All data is simulated.** `sim.py` generates 200,000 calls across 10 verification APIs for September 2026, with 4 planted problems, to test whether the method finds them. Competitor figures are invented. It is not real company data.

## What it does
- **Benchmarking (`q.sql`):** p50/p95 latency and success rate per API, compared with an internal target and a competitor. SQLite has no percentile function, so the percentiles come from window functions.
- **Failure analysis (`run.py`):** failure reasons, success rate by week, device tier and document language, conversion by client segment, and the completed onboardings lost to each fixable cause.

## Findings
- Passport OCR p95 is 2,786 ms vs a 2,000 ms target. It is the only API over its latency target, and 11.4% of its successful calls are slower than the target.
- 5 of 10 APIs fall below a 97% success standard, led by Aadhaar OCR at 93.0%.
- Three fixable causes cost about 1,520 completed onboardings in the month:
  - Face Match and Liveness on low-end Android (85.2% vs 96.2% success): ~700
  - Driving Licence registry timeouts, 15 to 21 Sep (82.1% vs 97.5%): ~470
  - Aadhaar OCR on Tamil and Bengali cards (82.3% vs 95.6%): ~350
- Client segment made no difference (96.2% to 96.3% success across all four), so the problem lives in the device, the document and the upstream source.
- The method found all 4 planted problems.

## Run
```
pip install -r requirements.txt
python sim.py   # builds verifybench.db
python run.py   # prints the benchmark and failure-analysis tables
python build_site.py   # rebuilds the results page in docs/
```

## Files
| File | What it is |
| --- | --- |
| `sim.py` | Generates the simulated API call log and the standards table |
| `q.sql` | Benchmark query: p50/p95 latency and success rate vs target and competitor |
| `run.py` | Runs the benchmark plus the failure-analysis queries |
| `build_site.py` | Builds the static results page (`docs/index.html`) served on GitHub Pages |
| `CASE_STUDY.pdf` | 6-page write-up with charts, OCR sourcing tracker and recommendations |

## Limits
The data is simulated with planted problems, competitor figures are invented, and conversion is modelled from two average rates. On a real call log, the same queries would run unchanged; only the standards and competitor figures would need real inputs.
