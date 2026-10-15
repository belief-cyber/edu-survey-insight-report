#!/usr/bin/env python3
"""Step 4b. Apply manual overrides and compute theme frequencies.

usage: python qual_finalize.py --work W
reads W/qual_auto.json, W/overrides.json → writes W/qual_final.json, W/qual_summary.md
Counts: mentions (code×row), unique respondents (비식별응답ID), related 교육 수.
Multi-coding is allowed, so percentages do not sum to 100%.
"""
import argparse, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from common import *

HERE = os.path.dirname(os.path.abspath(__file__))


def table(rows, codes):
    out = {}
    base = {r['rid'] for r in rows}
    for c in codes:
        hit = [r for r in rows if c in r['codes']]
        if not hit: continue
        rs = {r['rid'] for r in hit}
        out[c] = dict(mentions=len(hit), resp=len(rs), edus=len({r['edu'] for r in hit}),
                      pct=round(len(rs) / max(1, len(base)) * 100, 1), ids=[r['id'] for r in hit])
    return dict(base_rows=len(rows), base_resp=len(base), base_edus=len({r['edu'] for r in rows}), themes=out)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--work', required=True)
    ap.add_argument('--codebook', default=os.path.join(HERE, '..', 'assets', 'codebook.json'))
    o = ap.parse_args()
    cb = jload(o.codebook); codes = [c['code'] for c in cb['codes']]; lab = {c['code']: c['label'] for c in cb['codes']}
    auto = jload(os.path.join(o.work, 'qual_auto.json'))
    ov = {k: v for k, v in jload(os.path.join(o.work, 'overrides.json')).items() if not k.startswith('_')}
    ids = {r['id'] for r in auto['rows']}
    bad = [k for k in ov if k not in ids]
    unknown = sorted({c for v in ov.values() for c in v.get('add', []) + v.get('remove', []) if c != '*' and c not in codes})
    if bad or unknown:
        sys.exit(f'overrides 오류 — 없는 ID: {bad[:5]} / 없는 코드: {unknown}')
    rows = []
    for r in auto['rows']:
        c = set(r['auto'])
        if r['id'] in ov:
            v = ov[r['id']]
            if '*' in v.get('remove', []): c = set()
            c -= set(v.get('remove', [])); c |= set(v.get('add', []))
        r = dict(r, codes=sorted(c, key=codes.index), generic=len(c) == 0, reviewed=r['id'] in ov)
        rows.append(r)
    T = [r for r in rows if r['g'] == 'TARGET']; O = [r for r in rows if r['g'] == 'OTHER']
    res = dict(codebook=cb['version'], n_overrides=len(ov), rows=rows,
               target=table(T, codes), other=table(O, codes),
               other_by_year={y: table([r for r in O if r['edu'][:4] == y], codes) for y in sorted({r['edu'][:4] for r in O})},
               clusters={})
    for name, cs in cb['clusters'].items():
        for key, rr in [('target', T), ('other', O)]:
            hit = [r for r in rr if set(r['codes']) & set(cs)]
            res['clusters'].setdefault(name, {})[key] = dict(resp=len({r['rid'] for r in hit}), edus=len({r['edu'] for r in hit}),
                                                             by_year=dict(pd.Series([r['edu'][:4] for r in hit]).value_counts()) if hit else {})
    jdump(res, os.path.join(o.work, 'qual_final.json'))
    L = [f"# 주관식 주제 빈도 (overrides {len(ov)}건 반영)"]
    for name, tb in [('대상 교육', res['target']), ('그 외 교육', res['other'])]:
        L += ['', f"## {name}: 원문 {tb['base_rows']}행 · 응답자 {tb['base_resp']}명 · 교육 {tb['base_edus']}개"]
        for c, v in sorted(tb['themes'].items(), key=lambda x: -x[1]['resp']):
            L.append(f"- {lab[c]} ({c}): 응답자 {v['resp']}명 ({v['pct']}%), 언급 {v['mentions']}, 교육 {v['edus']} — 예: {', '.join(v['ids'][:4])}")
    L += ['', '## 묶음(cluster)'] + [f"- {k}: 대상 {v['target']} / 그 외 {v['other']}" for k, v in res['clusters'].items()]
    L += ['', f"일반 인사·내용 없음(코드 없음): 대상 {sum(r['generic'] for r in T)}행, 그 외 {sum(r['generic'] for r in O)}행",
          f"검토 기록이 없는 대상 행: {sum(1 for r in T if not r['reviewed'])} (대상 행은 모두 확인하고, 자동 코드가 맞으면 note만 남겨도 됨)"]
    open(os.path.join(o.work, 'qual_summary.md'), 'w', encoding='utf-8').write('\n'.join(L))
    print('\n'.join(L[:40]))


if __name__ == '__main__':
    main()
