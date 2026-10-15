#!/usr/bin/env python3
"""Step 4a. First-pass qualitative coding + full reading sheet.

usage: python qual_prep.py --work W [--codebook assets/codebook.json]
writes W/qual_auto.json   (every included original, masked, with candidate codes)
       W/qual_review.md   (reading sheet: TARGET first, then all others, grouped by 교육)
       W/overrides.json   (empty template if absent) — fill it after reading EVERY row.
The package's PROPOSED coding (주제/의견유형) is shown only as reference.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--work', required=True)
    ap.add_argument('--codebook', default=os.path.join(HERE, '..', 'assets', 'codebook.json'))
    o = ap.parse_args()
    ins = jload(os.path.join(o.work, 'inspect.json')); tgt = jload(os.path.join(o.work, 'target.json'))
    cb = jload(o.codebook)
    D = load(ins['pkg_dir'], ins['split_modes'])
    q, s, e = D['q'], D['s'], D['e']
    q = q[q['분석제외'] == 'N'].merge(s[['비식별응답ID', '응답자신분']], on='비식별응답ID', how='left')
    T = set(tgt['survey_ids'])
    rows, masklog = [], []
    for _, r in q.iterrows():
        raw = str(r['비식별원문'])
        t = mask_names(raw)
        if t.replace('○○○', '') != raw.replace('&quot;', '"').replace('&#039;', "'").replace('&amp;', '&'):
            masklog.append(dict(id=r['비식별주관식ID'], before=raw[:80], after=t[:80]))
        codes = [c['code'] for c in cb['codes'] if c['pattern'] and re.search(c['pattern'], t, flags=re.I)]
        qn = re.match(r'(Q\d+)', str(r['원문항']))
        rows.append(dict(id=r['비식별주관식ID'], rid=r['비식별응답ID'], edu=r['교육ID'], q=qn.group(1) if qn else '',
                         qt=str(r['원문항']), t=t, st=r['응답자신분'] if isinstance(r['응답자신분'], str) else '',
                         g='TARGET' if r['교육ID'] in T else 'OTHER', auto=codes,
                         pkg_theme=str(r.get('주제', '')), pkg_type=str(r.get('의견유형', ''))))
    jdump(dict(codebook=cb['version'], rows=rows, masklog=masklog), os.path.join(o.work, 'qual_auto.json'))
    lab = {c['code']: c['label'] for c in cb['codes']}
    L = ['# 주관식 전수 검토 시트', '', f"대상: {tgt['label']} · 포함 원문 {len(rows)}행 (대상 {sum(r['g']=='TARGET' for r in rows)}행)",
         '각 행을 모두 읽고 자동 후보 코드가 맞는지 판단해 overrides.json에 add/remove를 기록한다. 일반 인사만 있는 응답은 코드를 모두 제거한다.',
         '', '## 코드북']
    L += [f"- `{c['code']}` {c['label']} — {c['desc']}" for c in cb['codes']]
    if masklog:
        L += ['', '## 실명 마스킹 기록(오탐 여부 확인)'] + [f"- {m['id']}: {m['after']}" for m in masklog]
    for grp in ['TARGET', 'OTHER']:
        L += ['', f"## {'대상 교육' if grp == 'TARGET' else '그 외 교육'}"]
        cur = None
        for r in sorted([x for x in rows if x['g'] == grp], key=lambda x: (x['edu'], x['id'])):
            if r['edu'] != cur:
                cur = r['edu']; L.append(f"\n### {cur}")
            L.append(f"- `{r['id']}` [{r['st']}·{r['q']}] {r['t']}\n  - 자동: {', '.join(r['auto']) or '없음'} | 패키지(PROPOSED): {r['pkg_theme']} / {r['pkg_type']}")
    open(os.path.join(o.work, 'qual_review.md'), 'w', encoding='utf-8').write('\n'.join(L))
    ov = os.path.join(o.work, 'overrides.json')
    if not os.path.exists(ov):
        jdump({"_format": "{\"<비식별주관식ID>\": {\"add\": [codes], \"remove\": [codes], \"note\": \"사유\"}}  · 'remove': ['*'] = 모든 코드 제거(일반 인사)"}, ov)
    print(f"원문 {len(rows)}행 → qual_review.md 작성. 마스킹 {len(masklog)}건. 이제 전 행을 읽고 overrides.json을 작성하세요.")


if __name__ == '__main__':
    main()
