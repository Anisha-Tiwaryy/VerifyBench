"""Run the benchmark (q.sql) and failure-analysis queries against verifybench.db."""
import sqlite3, pandas as pd

pd.set_option('display.width', 200)
con = sqlite3.connect('verifybench.db')
print('Benchmark: latency and success rate per API\n')
print(pd.read_sql(open('q.sql').read(), con).to_string(index=False))

queries = {
    'Driving Licence Verify, success rate by week':
        "SELECT (day-1)/7+1 AS week, ROUND(100.0*AVG(status='success'),1) AS success_pct, COUNT(*) AS calls "
        "FROM api_calls WHERE api='Driving Licence Verify' AND day<=28 GROUP BY week",
    'Failure reasons':
        "SELECT failure_reason, COUNT(*) AS n, ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM api_calls WHERE status='fail'),1) AS pct "
        "FROM api_calls WHERE status='fail' GROUP BY 1 ORDER BY n DESC",
    'Face Match and Liveness by device segment':
        "SELECT channel||' '||device_tier AS segment, ROUND(100.0*AVG(status='success'),1) AS success_pct, "
        "ROUND(100.0*AVG(completed),1) AS conversion_pct, COUNT(*) AS calls "
        "FROM api_calls WHERE api IN ('Face Match','Liveness Check') GROUP BY 1 ORDER BY conversion_pct",
    'Aadhaar OCR by document language':
        "SELECT doc_language, ROUND(100.0*AVG(status='success'),1) AS success_pct, "
        "ROUND(100.0*AVG(completed),1) AS conversion_pct, COUNT(*) AS calls "
        "FROM api_calls WHERE api='Aadhaar OCR' GROUP BY 1 ORDER BY success_pct",
    'Conversion by client segment':
        "SELECT client_segment, ROUND(100.0*AVG(status='success'),1) AS success_pct, ROUND(100.0*AVG(completed),1) AS conversion_pct "
        "FROM api_calls GROUP BY 1",
    'Overall':
        "SELECT ROUND(100.0*AVG(completed),1) AS conversion_pct, ROUND(100.0*AVG(status='success'),1) AS success_pct, "
        "SUM(status='fail') AS failed_calls FROM api_calls",
}
for title, q in queries.items():
    print(f'\n{title}\n')
    print(pd.read_sql(q, con).to_string(index=False))

# Completions lost per fixable cause
d = pd.read_sql('SELECT * FROM api_calls', con)
cs = d[d.status == 'success'].completed.mean(); cf = d[d.status == 'fail'].completed.mean()

def lost(mask, base):
    seg_ok = d[mask].status.eq('success').mean(); base_ok = d[base].status.eq('success').mean()
    return round((base_ok - seg_ok) * mask.sum() * (cs - cf))

fm = d.api.isin(['Face Match', 'Liveness Check']); dl = d.api == 'Driving Licence Verify'; aa = d.api == 'Aadhaar OCR'
wk3 = d.day.between(15, 21); reg = d.doc_language.isin(['Tamil', 'Bengali'])
causes = {
    'Low-end Android face/liveness capture': lost(fm & (d.device_tier == 'low-end'), fm & (d.device_tier != 'low-end')),
    'Driving Licence registry timeouts (15-21 Sep)': lost(dl & wk3, dl & ~wk3),
    'Aadhaar OCR on Tamil/Bengali cards': lost(aa & reg, aa & ~reg),
}
print('\nCompleted onboardings lost per fixable cause\n')
for k, v in causes.items():
    print(f'  {k}: ~{v:,}')
print(f'  Total: ~{sum(causes.values()):,}')
po = d[(d.api == 'Passport OCR') & (d.status == 'success')]
print(f'\nPassport OCR successful calls over 2,000 ms target: {100 * po.latency_ms.gt(2000).mean():.1f}%')
