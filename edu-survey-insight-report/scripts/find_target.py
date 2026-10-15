#!/usr/bin/env python3
"""Step 2. Resolve the target education group from a name/keyword.

usage: python find_target.py --work W --query "월간 AI 한입" [--year 2026] [--ids A,B] [--label "..."]
       [--similar "AI,GPT,프롬프트"]  (keywords in 교육명/교육군 for the 'similar-topic' comparison group)
Matching: 교육명, 교육ID, 교육유형, 교육군 key (spaces ignored, case-insensitive).
writes W/target.json. Always show the printed list to the user when more than one 교육군 matched.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *


def norm(x):
    return re.sub(r'\s+', '', str(x)).lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--query', default='')
    ap.add_argument('--year', default='')
    ap.add_argument('--ids', default='')
    ap.add_argument('--label', default='')
    ap.add_argument('--similar', default='')
    ap.add_argument('--purpose', default='')
    o = ap.parse_args()
    ins = jload(os.path.join(o.work, 'inspect.json'))
    D = load(ins['pkg_dir'], ins['split_modes'])
    e = D['e']
    if o.ids:
        hit = e[e['교육ID'].isin(o.ids.split(','))]
    else:
        qn = norm(o.query)
        m = e.apply(lambda r: any(qn in norm(r[c]) for c in ['교육명', '교육ID', '교육유형', 'serkey']), axis=1)
        hit = e[m]
    if o.year:
        hit = hit[hit['yr'].isin(o.year.split(','))]
    if hit.empty:
        sys.exit('일치하는 교육이 없습니다. inspect.json의 교육군 목록에서 serkey나 교육ID를 확인하세요.')
    cols = ['교육ID', '교육명', 'yr', '교육유형', '운영방식', 'date', '교육대상', '신청자수_기준표', '참여자수_기준표', '설문응답수', 'split']
    print(hit[cols].to_string(index=False))
    sers = hit['serkey'].unique().tolist()
    if len(sers) > 1:
        print('\n[확인 필요] 여러 교육군이 일치했습니다:', sers, '→ 사용자에게 범위를 확인하거나 --ids/--year로 좁히세요.')
    nos = hit[hit['설문응답수'].fillna(0) == 0]['교육ID'].tolist()
    names = hit['교육명'].astype(str).str.replace(r'-\d+$', '', regex=True).unique()
    if o.label: label = o.label
    elif hit['교육유형'].nunique() == 1 and hit['교육유형'].iloc[0] not in ('자체교육', '특강', '워크숍', '영상'): label = hit['교육유형'].iloc[0]
    elif len(names) == 1: label = names[0]
    else: label = f"{'·'.join(sers)} 교육군"
    if not o.label: print(f'표시명 자동 지정: {label} (바꾸려면 --label)')
    t = dict(label=label, query=o.query, purpose=o.purpose, ids=hit['교육ID'].tolist(),
             survey_ids=[i for i in hit['교육ID'] if i not in nos], no_survey_ids=nos,
             series=sers, years=sorted(hit['yr'].unique().tolist()),
             similar_keywords=[k.strip() for k in o.similar.split(',') if k.strip()])
    jdump(t, os.path.join(o.work, 'target.json'))
    print(f"\n대상: {label} | 교육 {len(t['ids'])}개 (설문 {len(t['survey_ids'])}) | 연도 {t['years']} | 유사 키워드 {t['similar_keywords'] or '없음'}")
    if nos: print('설문 없음(분석 제외):', nos)


if __name__ == '__main__':
    main()
