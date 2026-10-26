"""Simulate one month (Sep 2026) of identity verification API traffic into SQLite.

All data is simulated, with 4 planted problems, to test whether the
benchmarking and failure-analysis method finds them. Competitor figures are invented.
"""
import numpy as np, pandas as pd, sqlite3

rng = np.random.default_rng(42)
apis = {  # name: (base_ms, sd, success, target_p95, competitor_p95)
    'PAN Verify': (180, 60, 0.985, 600, 520),
    'Aadhaar OCR': (900, 250, 0.955, 1800, 1650),
    'Passport OCR': (1100, 300, 0.960, 2000, 1700),
    'Driving Licence Verify': (400, 120, 0.975, 1200, 1100),
    'Bank Account Verify': (1500, 500, 0.970, 4000, 3600),
    'Face Match': (350, 90, 0.965, 900, 800),
    'Liveness Check': (600, 150, 0.960, 1500, 1300),
    'Mobile Intelligence': (120, 40, 0.990, 400, 380),
    'Device Intelligence': (90, 30, 0.992, 300, 320),
    'Email Risk': (150, 50, 0.988, 500, 450),
}
N = 200000
api = rng.choice(list(apis), N)
seg = rng.choice(['Lending', 'Fintech', 'Gaming', 'E-commerce'], N, p=[.35, .3, .2, .15])
chan = rng.choice(['Android', 'iOS', 'Web'], N, p=[.6, .2, .2])
tier = np.where(chan == 'Android', rng.choice(['low-end', 'mid', 'high-end'], N, p=[.4, .4, .2]), 'high-end')
lang = rng.choice(['English', 'Hindi', 'Tamil', 'Bengali', 'Marathi'], N, p=[.5, .2, .1, .1, .1])
day = rng.integers(1, 31, N)
ts = pd.to_datetime('2026-09-01') + pd.to_timedelta(day - 1, 'D') + pd.to_timedelta(rng.integers(0, 86400, N), 's')
lat = np.zeros(N); ok = np.ones(N, bool); reason = np.array([''] * N, dtype=object)
for a, (b, sd, s, _, _) in apis.items():
    m = api == a; n = m.sum()
    lat[m] = rng.lognormal(np.log(b), sd / b, n)
    ok[m] = rng.random(n) < s

# Planted 1: Passport OCR slow tail (p95 over target)
m = (api == 'Passport OCR'); slow = m & (rng.random(N) < .12); lat[slow] *= 2.4
# Planted 2: Driving Licence source registry timeouts, 15-21 Sep
m = (api == 'Driving Licence Verify') & (day >= 15) & (day <= 21); f = m & (rng.random(N) < .16)
ok[f] = False; reason[f] = 'Source registry timeout'; lat[f] = rng.uniform(5000, 8000, f.sum())
# Planted 3: Face Match and Liveness fail on low-end Android (low light / blur)
m = np.isin(api, ['Face Match', 'Liveness Check']) & (tier == 'low-end'); f = m & (rng.random(N) < .11)
ok[f] = False; reason[f] = 'Low light or blur'
# Planted 4: Aadhaar OCR on regional-script cards
m = (api == 'Aadhaar OCR') & np.isin(lang, ['Tamil', 'Bengali']); f = m & (rng.random(N) < .14)
ok[f] = False; reason[f] = 'Unsupported regional script'

# Remaining failure reasons
rem = (~ok) & (reason == '')
reason[rem] = rng.choice(['Invalid or expired document', 'Name mismatch', 'Image cropped', 'Upstream 5xx'],
                         rem.sum(), p=[.35, .3, .2, .15])
reason[ok] = None
# Conversion: did the user complete onboarding?
conv = np.where(ok, rng.random(N) < .88, rng.random(N) < .22)

df = pd.DataFrame(dict(txn_id=np.arange(N), ts=ts.astype(str), day=day, api=api, client_segment=seg,
                       channel=chan, device_tier=tier, doc_language=lang,
                       status=np.where(ok, 'success', 'fail'), failure_reason=reason,
                       latency_ms=lat.round().astype(int), completed=conv.astype(int)))
con = sqlite3.connect('verifybench.db')
df.to_sql('api_calls', con, if_exists='replace', index=False)
pd.DataFrame([(a, v[3], 0.97, v[4]) for a, v in apis.items()],
             columns=['api', 'target_p95_ms', 'target_success', 'competitor_p95_ms']
             ).to_sql('standards', con, if_exists='replace', index=False)
print(f'Wrote {len(df):,} API calls to verifybench.db')
