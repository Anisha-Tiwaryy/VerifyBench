"""Build a static results dashboard (docs/index.html) for GitHub Pages.

Run after sim.py:  python build_site.py
"""
import sqlite3, os, html
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

os.makedirs('docs', exist_ok=True)
con = sqlite3.connect('verifybench.db')
ACC, MUTE, INK, GRID = '#C2410C', '#9CA3AF', '#111827', '#E5E7EB'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.edgecolor': GRID,
                     'axes.labelcolor': INK, 'xtick.color': '#4B5563', 'ytick.color': INK})

bench = pd.read_sql(open('q.sql').read(), con)
bench['ratio'] = bench.p95 / bench.target_p95_ms
bench = bench.sort_values('ratio')

# Chart 1: p95 latency as % of target
fig, ax = plt.subplots(figsize=(7.5, 4))
ax.barh(bench.api, bench.ratio * 100, color=[ACC if r > 1 else MUTE for r in bench.ratio], height=0.6)
ax.axvline(100, color=INK, ls='--', lw=1)
ax.text(101, len(bench) - 0.5, 'target', fontsize=9, color=INK)
for y, (r, p) in enumerate(zip(bench.ratio, bench.p95)):
    ax.text(r * 100 + 2, y, f'{p:,} ms', va='center', fontsize=9)
ax.set_xlabel('p95 latency as % of internal target')
ax.spines[['top', 'right']].set_visible(False); ax.grid(axis='x', color=GRID); ax.set_axisbelow(True)
ax.set_xlim(0, 165)
fig.tight_layout(); fig.savefig('docs/latency.png', dpi=160); plt.close(fig)

# Chart 2: success rate vs 97% standard
b2 = bench.sort_values('success_pct')
fig, ax = plt.subplots(figsize=(7.5, 4))
ax.barh(b2.api, b2.success_pct, color=[ACC if s < 97 else MUTE for s in b2.success_pct], height=0.6)
ax.axvline(97, color=INK, ls='--', lw=1)
ax.text(97.1, len(b2) - 0.5, '97% standard', fontsize=9, color=INK)
for y, s in enumerate(b2.success_pct):
    ax.text(s + 0.1, y, f'{s:.1f}%', va='center', fontsize=9)
ax.set_xlim(90, 100.8); ax.set_xlabel('Success rate (%)')
ax.spines[['top', 'right']].set_visible(False); ax.grid(axis='x', color=GRID); ax.set_axisbelow(True)
fig.tight_layout(); fig.savefig('docs/success.png', dpi=160); plt.close(fig)

# Chart 3: failure reasons
fr = pd.read_sql("SELECT failure_reason, COUNT(*) n FROM api_calls WHERE status='fail' GROUP BY 1 ORDER BY n", con)
fixable = {'Low light or blur', 'Upstream 5xx', 'Source registry timeout', 'Unsupported regional script'}
fig, ax = plt.subplots(figsize=(7.5, 3.6))
ax.barh(fr.failure_reason, fr.n, color=[ACC if r in fixable else MUTE for r in fr.failure_reason], height=0.6)
tot = fr.n.sum()
for y, n in enumerate(fr.n):
    ax.text(n + 20, y, f'{n:,} ({n / tot:.0%})', va='center', fontsize=9)
ax.set_xlim(0, fr.n.max() * 1.25); ax.set_xlabel('Failed calls')
ax.spines[['top', 'right']].set_visible(False); ax.grid(axis='x', color=GRID); ax.set_axisbelow(True)
fig.tight_layout(); fig.savefig('docs/failures.png', dpi=160); plt.close(fig)

# Chart 4: DL weekly success
wk = pd.read_sql("SELECT (day-1)/7+1 AS week, ROUND(100.0*AVG(status='success'),1) s FROM api_calls "
                 "WHERE api='Driving Licence Verify' AND day<=28 GROUP BY week", con)
fig, ax = plt.subplots(figsize=(7.5, 3))
ax.plot(wk.week, wk.s, marker='o', color=ACC, lw=2)
for x, s in zip(wk.week, wk.s):
    ax.text(x, s + 1 if s > 90 else s - 3, f'{s}%', ha='center', fontsize=9)
ax.axhline(97, color=INK, ls='--', lw=1)
ax.set_xticks(wk.week, [f'Week {w}' for w in wk.week]); ax.set_ylim(78, 101); ax.set_ylabel('Success rate (%)')
ax.spines[['top', 'right']].set_visible(False); ax.grid(axis='y', color=GRID); ax.set_axisbelow(True)
fig.tight_layout(); fig.savefig('docs/dl_weekly.png', dpi=160); plt.close(fig)

# Lost onboardings per fixable cause
d = pd.read_sql('SELECT * FROM api_calls', con)
cs = d[d.status == 'success'].completed.mean(); cf = d[d.status == 'fail'].completed.mean()
def cut(mask, base):
    so = d[mask].status.eq('success').mean(); bo = d[base].status.eq('success').mean()
    return so, bo, int(mask.sum()), round((bo - so) * mask.sum() * (cs - cf))
fm = d.api.isin(['Face Match', 'Liveness Check']); dl = d.api == 'Driving Licence Verify'; aa = d.api == 'Aadhaar OCR'
wk3 = d.day.between(15, 21); reg = d.doc_language.isin(['Tamil', 'Bengali'])
causes = [
    ('Face Match and Liveness on low-end Android', *cut(fm & (d.device_tier == 'low-end'), fm & (d.device_tier != 'low-end')), 'Low light and blur from weak phone cameras'),
    ('Driving Licence Verify, 15 to 21 Sep', *cut(dl & wk3, dl & ~wk3), 'Government source registry timing out'),
    ('Aadhaar OCR on Tamil and Bengali cards', *cut(aa & reg, aa & ~reg), 'OCR model not trained on these scripts'),
]
total_lost = sum(c[4] for c in causes)
below = int((bench.success_pct < 97).sum())
po = d[(d.api == 'Passport OCR') & (d.status == 'success')]
slow_pct = 100 * po.latency_ms.gt(2000).mean()
passport = bench[bench.api == 'Passport OCR'].iloc[0]

e = html.escape
bench_rows = ''.join(
    f"<tr><td>{e(r.api)}</td><td>{r.calls:,}</td><td>{r.p50:,}</td>"
    f"<td class='{'bad' if r.p95 > r.target_p95_ms else ''}'>{r.p95:,}</td><td>{r.target_p95_ms:,}</td>"
    f"<td>{r.competitor_p95_ms:,}</td><td class='{'bad' if r.success_pct < 97 else ''}'>{r.success_pct:.1f}%</td></tr>"
    for r in bench.sort_values('ratio', ascending=False).itertuples())
cause_rows = ''.join(
    f"<tr><td>{e(c[0])}</td><td>{c[1]:.1%} vs {c[2]:.1%}</td><td>{c[3]:,}</td><td>~{c[4]:,}</td><td>{e(c[5])}</td></tr>"
    for c in causes)

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>VerifyBench</title>
<meta name="description" content="Benchmarking 10 identity verification APIs on latency and success rate, and tracing why verifications fail.">
<style>
:root {{ --ink:#111827; --muted:#4B5563; --line:#E5E7EB; --acc:#C2410C; --bg:#FFFFFF; --soft:#F9FAFB; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.6 -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }}
main {{ max-width:860px; margin:0 auto; padding:40px 16px 64px; }}
h1 {{ font-size:30px; line-height:1.2; margin:0 0 8px; }}
h2 {{ font-size:21px; margin:44px 0 10px; }}
p {{ margin:0 0 12px; }}
.sub {{ color:var(--muted); margin-bottom:20px; }}
.note {{ background:var(--soft); border-left:3px solid var(--acc); padding:10px 14px; color:var(--muted); font-size:14px; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin:24px 0; }}
.kpi {{ border:1px solid var(--line); border-radius:8px; padding:14px; }}
.kpi b {{ display:block; font-size:26px; color:var(--acc); line-height:1.2; }}
.kpi span {{ font-size:14px; color:var(--muted); }}
img {{ width:100%; height:auto; border:1px solid var(--line); border-radius:8px; margin:8px 0 6px; }}
.cap {{ font-size:13px; color:var(--muted); margin-bottom:16px; }}
.tbl {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; margin:8px 0 16px; }}
th, td {{ text-align:left; padding:7px 8px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ font-weight:600; background:var(--soft); }}
td.bad {{ color:var(--acc); font-weight:600; }}
pre {{ background:var(--soft); border:1px solid var(--line); border-radius:8px; padding:12px; overflow-x:auto; font-size:13px; }}
a {{ color:var(--acc); }}
ol li {{ margin-bottom:8px; }}
footer {{ margin-top:48px; padding-top:16px; border-top:1px solid var(--line); font-size:14px; color:var(--muted); }}
</style></head><body><main>
<h1>VerifyBench: Benchmarking Identity Verification APIs</h1>
<p class="sub">How I would benchmark verification APIs on latency and success rate, explain why verifications fail, and decide what to fix first. By Anisha Tiwary.</p>
<p class="note">All data is simulated: 200,000 calls across 10 APIs for September 2026, with 4 problems planted to test whether the method finds them. It found all 4. Competitor figures are invented.</p>

<div class="kpis">
<div class="kpi"><b>{passport.p95:,} ms</b><span>Passport OCR p95 vs a {passport.target_p95_ms:,} ms target</span></div>
<div class="kpi"><b>{below} of 10</b><span>APIs below the 97% success standard</span></div>
<div class="kpi"><b>~{total_lost:,}</b><span>onboardings lost to 3 fixable causes in a month</span></div>
<div class="kpi"><b>4 of 4</b><span>planted problems found by the method</span></div>
</div>

<h2>1. Latency: one API breaks its target</h2>
<p>Passport OCR is the only API over its latency target, and {passport.p95 - passport.competitor_p95_ms:,} ms slower than the competitor at p95. {slow_pct:.1f}% of its successful calls exceed the target. Every other API beats both its target and the competitor.</p>
<img src="latency.png" alt="p95 latency as a percentage of target for each API; Passport OCR is the only one above 100%">
<p class="cap">p95 of successful-call latency per API, as a share of its internal target.</p>

<h2>2. Success rate: five APIs miss the standard</h2>
<img src="success.png" alt="Success rate per API; five APIs fall below 97%">
<div class="tbl"><table><tr><th>API</th><th>Calls</th><th>p50 ms</th><th>p95 ms</th><th>Target p95</th><th>Competitor p95</th><th>Success</th></tr>{bench_rows}</table></div>
<p>SQLite has no percentile function, so p50 and p95 come from window functions:</p>
<pre>WITH ranked AS (
  SELECT api, latency_ms,
         ROW_NUMBER() OVER (PARTITION BY api ORDER BY latency_ms) AS rn,
         COUNT(*)     OVER (PARTITION BY api) AS n
  FROM api_calls WHERE status = 'success'
)
SELECT api,
  MAX(CASE WHEN rn = CAST(0.50 * n AS INT) THEN latency_ms END) AS p50,
  MAX(CASE WHEN rn = CAST(0.95 * n AS INT) THEN latency_ms END) AS p95
FROM ranked GROUP BY api;</pre>

<h2>3. Why did verifications fail?</h2>
<p>Users who fail a verification complete onboarding {cf:.0%} of the time, against {cs:.0%} for users who pass. Cutting success rate by device, week and document language finds three clusters:</p>
<img src="failures.png" alt="Failed calls by reason; orange reasons are fixable by the platform">
<p class="cap">Orange: causes the platform can fix (capture, upstream, OCR coverage). Grey: user-side.</p>
<div class="tbl"><table><tr><th>Where it fails</th><th>Success: segment vs rest</th><th>Calls</th><th>Onboardings lost</th><th>Likely cause</th></tr>{cause_rows}</table></div>
<img src="dl_weekly.png" alt="Driving Licence Verify success rate by week, dropping to 82.1% in week 3">
<p class="cap">A weekly success-rate check catches an upstream outage like the Driving Licence registry drop in week 3.</p>
<p>Client segment made no difference: Lending, Fintech, Gaming and E-commerce all sit at 96.2% to 96.3% success. The problem lives in the device, the document and the upstream source.</p>

<h2>4. What I would fix first</h2>
<ol>
<li><b>Light and blur check before Face Match and Liveness upload</b> on low-end Android, with a retake prompt (Engineering). ~{causes[0][4]:,} onboardings a month.</li>
<li><b>Alert on a 3-point weekly success drop</b>, plus retry with backoff and a fallback source for registry timeouts (Engineering). ~{causes[1][4]:,} onboardings in an outage week.</li>
<li><b>Source and tag Tamil and Bengali Aadhaar cards</b>, then retrain OCR (Product, data). ~{causes[2][4]:,} onboardings a month.</li>
<li><b>Profile Passport OCR's slow tail</b> by document layout to close the gap to the competitor (Engineering).</li>
<li><b>One weekly benchmark view for every API</b> using these checks (Product analytics).</li>
</ol>

<footer>
Code, SQL and the full 6-page case study: <a href="https://github.com/Anisha-Tiwaryy/VerifyBench">github.com/Anisha-Tiwaryy/VerifyBench</a> (<a href="https://github.com/Anisha-Tiwaryy/VerifyBench/blob/main/CASE_STUDY.pdf">case study PDF</a>)<br>
Anisha Tiwary · <a href="https://anisha-tiwaryy.github.io">anisha-tiwaryy.github.io</a> · <a href="https://www.linkedin.com/in/anisha-tiwary-94b89030a">LinkedIn</a>
</footer>
</main></body></html>"""
open('docs/index.html', 'w', encoding='utf-8').write(page)
print('Wrote docs/index.html')
