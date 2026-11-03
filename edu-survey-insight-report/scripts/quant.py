#!/usr/bin/env python3
"""Step 3. Quantitative analysis with the package rules.

usage: python quant.py --work W
reads W/inspect.json, W/target.json → writes W/quant_results.json, W/quant_summary.md
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *
try:
    from scipy import stats as sstats
except Exception:  # scipy optional
    sstats = None


def metric_block(a, m, by=None):
    d = integrated(a, m)
    out = {}
    groups = [('전체', d)] if by is None else list(d.groupby(by))
    for k, g in groups:
        out[str(k)] = dict(row=agg_values(g, 'row'), person=agg_values(g, 'person'), eqw=edu_equal(g), edus=int(g['교육ID'].nunique()))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--work', required=True); o = ap.parse_args()
    ins = jload(os.path.join(o.work, 'inspect.json')); tgt = jload(os.path.join(o.work, 'target.json'))
    D = load(ins['pkg_dir'], ins['split_modes']); e, s, a, q, qs = D['e'], D['s'], D['a'], D['q'], D['qs']
    T = set(tgt['survey_ids'])
    e['cmp'] = cmp_labels(e, T, tgt['similar_keywords'], tgt['years'])
    a = a.merge(e[['교육ID', 'cmp']], on='교육ID', how='left')
    R = {}
    # 1. official reproduction
    off = qs[qs['집계수준'] == '전체교육']
    chk = []
    for _, r in off.iterrows():
        m = r['표준분석항목ID']; d = integrated(a, m)
        st = agg_values(d); eq = edu_equal(d)
        ok = st['n'] == int(r['유효응답수']) and abs(st['mean'] - r['평균']) < 6e-4 and abs(eq - r['교육동일가중평균']) < 6e-4
        chk.append(dict(metric=m, official_n=int(r['유효응답수']), n=st['n'], official_mean=float(r['평균']), mean=st['mean'],
                        official_eqw=float(r['교육동일가중평균']), eqw=eq, edus=int(d['교육ID'].nunique()), ok=bool(ok)))
    R['official_check'] = chk
    # 2. overall & dims
    R['overall'] = {m: metric_block(a, m)['전체'] for m in METRICS}
    MET = [m for m in METRICS if len(integrated(a, m))]   # metrics present in this package
    R['metrics_present'] = MET
    R['by'] = {dim: {m: metric_block(a, m, col) for m in MET} for dim, col in
               [('연도', 'yr'), ('교육유형', '교육유형'), ('운영방식', '운영방식'), ('운영방식(v2 표기)', 'mode2'),
                ('응답자신분', '응답자신분'), ('비교군', 'cmp'), ('설문버전', '설문버전')]}
    # standard survey v2 linkage: metrics answered in both v1 and v2 wording → trend is conditional (B)
    vv = valid(a)
    both = vv.groupby('표준분석항목ID')['설문버전'].nunique()
    R['version_mix'] = dict(v2_answers=int((a['설문버전'] == 'v2').sum()), v2_educations=sorted(a[a['설문버전'] == 'v2']['교육ID'].unique().tolist()),
                            mixed_metrics=[m for m in MET if both.get(m, 0) > 1],
                            items=None if D['items'] is None else D['items'][['번호', '표준분석항목ID', '기존연결']].to_dict('records'))
    # bipolar difficulty (v2) — share easy / appropriate / hard, never a mean ranking
    bd = integrated(a, BIPOLAR)
    R['bipolar'] = None if bd.empty else dict(overall=bipolar(bd), person=bipolar(bd, 'person'),
                                              target=bipolar(bd[bd['교육ID'].isin(T)]),
                                              by_edu={k: bipolar(g) for k, g in bd[bd['교육ID'].isin(T)].groupby('교육ID')},
                                              by_cmp={k: bipolar(g, 'person') for k, g in bd.merge(e[['교육ID']], on='교육ID').groupby('cmp')})
    # target audience vs actual respondents (all)
    se = s.merge(e[['교육ID', '교육대상', 'yr']], on='교육ID')
    R['audience_mismatch'] = se.groupby(['교육대상', '응답자신분']).size().unstack(fill_value=0).to_dict('index')
    # 3. target deep dive
    ta = a[a['교육ID'].isin(T)]; tv = valid(ta)
    per = []
    for eid in tgt['survey_ids']:
        row = e[e['교육ID'] == eid].iloc[0]
        rs = s[s['교육ID'] == eid]
        item = dict(id=eid, name=row['교육명'], date=row['date'], mode=row['운영방식'], target=row['교육대상'],
                    app=None if pd.isna(row['신청자수_기준표']) else int(row['신청자수_기준표']),
                    part=None if pd.isna(row['참여자수_기준표']) else int(row['참여자수_기준표']),
                    resp=int(len(rs)), persons=int(rs['person'].nunique()), status=rs['응답자신분'].value_counts().to_dict(),
                    rr=None if row['응답률계산가능'] != 'Y' else float(row['응답률']), split=bool(row['split']), metrics={}, items=[])
        for m in MET:
            item['metrics'][m] = agg_values(integrated(ta[ta['교육ID'] == eid], m))
            src = tv[(tv['교육ID'] == eid) & (tv['표준분석항목ID'] == m)]
            if src['원본문항ID'].nunique() > 1 or m == 'goal_attainment':
                for (qid, txt), g in src.groupby(['원본문항ID', '원문항']):
                    item['items'].append(dict(metric=m, qid=qid, text=txt, **agg_values(g)))
        per.append(item)
    R['target_edus'] = per
    pooled = {}
    for m in MET:
        d = integrated(ta, m)
        st = dict(row=agg_values(d), person=agg_values(d, 'person'), eqw=edu_equal(d), edus=int(d['교육ID'].nunique()))
        if sstats is not None and d['교육ID'].nunique() > 1:
            try:
                st['kruskal_p'] = round(float(sstats.kruskal(*[g['val'].values for _, g in d.groupby('교육ID')]).pvalue), 4)
            except Exception:
                st['kruskal_p'] = None
        st['by_status'] = {k: agg_values(g) for k, g in d.groupby('응답자신분')}
        pooled[m] = st
    R['target_pooled'] = pooled
    ch = ta[ta['표준분석항목ID'] == 'awareness_channel']['원본응답값'].map(norm_channel)
    R['target_channels'] = ch.value_counts().to_dict()
    # profile (신청 정보) breakdown: category share + key metric means by category (respondent join)
    prof = {}
    for item, ko in PROFILE_ITEMS.items():
        pv = profile_values(a, item)
        if pv.empty: continue
        out = {}
        for scope, ids in (('대상', T), ('전체', None)):
            sub = pv if ids is None else pv[pv['비식별응답ID'].isin(set(ta['비식별응답ID']))]
            if sub.empty: continue
            cats = {}
            for cat, g in sub.groupby('cat'):
                rid = set(g['비식별응답ID']); row = dict(n=int(len(rid)))
                for m in ('overall_satisfaction', 'goal_attainment', 'perceived_practical_help'):
                    d = integrated(a[a['비식별응답ID'].isin(rid)], m)
                    if len(d): row[m] = dict(mean=round(float(d['val'].mean()), 4), n=int(len(d)), le3=agg_values(d)['le3'])
                d = integrated(a[a['비식별응답ID'].isin(rid)], BIPOLAR)
                if len(d): row[BIPOLAR] = bipolar(d)
                cats[str(cat)] = row
            out[scope] = cats
        prof[item] = dict(label=ko, scopes=out)
    R['profile'] = prof
    # target official per-item reproduction
    offe = qs[(qs['집계수준'] != '전체교육') & qs['교육ID'].isin(T)]
    mism = []
    for _, r in offe.iterrows():
        g = tv[(tv['교육ID'] == r['교육ID']) & (tv['원문항'] == r['원문항']) & (tv['표준분석항목ID'] == r['표준분석항목ID'])]
        if len(g) != int(r['유효응답수']) or abs(g['val'].mean() - r['평균']) > 6e-4:
            mism.append(dict(edu=r['교육ID'], item=r['원문항'][:40], official=(int(r['유효응답수']), float(r['평균'])), recalc=(len(g), round(float(g['val'].mean()), 3) if len(g) else None)))
    R['target_item_check'] = dict(rows=int(len(offe)), mismatches=mism)
    # 4. anomalies
    v = valid(a)
    wide = v.pivot_table(index=['비식별응답ID', '교육ID', 'yr'], columns='표준분석항목ID', values='val', aggfunc='min').reset_index()
    wide['tgt'] = wide['교육ID'].isin(T)
    mcols = [m for m in MET if m in wide]
    bim = []
    for m in [c for c in mcols if c != BIPOLAR]:   # bipolar 1/5 = very easy/hard, not an anomaly
        for yr, g in wide.groupby('yr'):
            x = g[m].dropna()
            if len(x) < 20: continue
            p1, p2 = (x == 1).mean(), (x == 2).mean()
            hi = g[(g.get('overall_satisfaction') == 5)][m].dropna()
            flag = p1 >= 0.10 and p1 >= 5 * max(p2, 0.004)
            bim.append(dict(metric=m, yr=yr, n=int(len(x)), p1=round(float(p1), 3), p2=round(float(p2), 3),
                            p1_among_overall5=round(float((hi == 1).mean()), 3) if len(hi) else None, flag=bool(flag)))
    R['bimodal_check'] = bim
    single = []
    for m in [c for c in mcols if c not in DIFFICULTY]:
        others = [c for c in mcols if c != m and c not in DIFFICULTY]
        if not others: continue
        cond_all5 = (wide[others].fillna(5) == 5).all(axis=1) & wide[others].notna().any(axis=1)
        hit = wide[cond_all5 & (wide[m] == 1)]
        base_t = wide[cond_all5 & wide['tgt'] & wide[m].notna()]; base_o = wide[cond_all5 & ~wide['tgt'] & wide[m].notna()]
        single.append(dict(metric=m, target_n=int(len(base_t)), target_hits=hit[hit['tgt']]['비식별응답ID'].tolist(),
                           other_n=int(len(base_o)), other_hits=int((~hit['tgt']).sum())))
    R['single_item_extreme'] = single
    low = wide[(wide.get('overall_satisfaction') <= 2)]
    lowc = []
    for _, r in low.iterrows():
        nlow = sum(1 for c in mcols if c not in DIFFICULTY and r.get(c) is not None and not pd.isna(r.get(c)) and r[c] <= 2)
        texts = q[(q['비식별응답ID'] == r['비식별응답ID']) & (q['분석제외'] == 'N')]['비식별원문'].astype(str).tolist()
        lowc.append(dict(rid=r['비식별응답ID'], edu=r['교육ID'], target=bool(r['tgt']), low_items=nlow,
                         scores={c: (None if pd.isna(r.get(c)) else int(r[c])) for c in mcols}, texts=[t[:160] for t in texts]))
    R['low_score_respondents'] = lowc
    # 5. split units
    sp = e[e['split']]
    R['split_units'] = dict(units=int(sp['unit'].nunique()), edus=int(len(sp)),
                            rows=int(s[s['교육ID'].isin(sp['교육ID'])].shape[0]),
                            persons=int(s[s['교육ID'].isin(sp['교육ID'])]['person'].nunique()),
                            by_year={yr: dict(rows=int((s.merge(e[['교육ID', 'yr']], on='교육ID')['yr'] == yr).sum()),
                                              persons=int(s.merge(e[['교육ID', 'yr']], on='교육ID').query('yr==@yr')['person'].nunique()))
                                     for yr in sorted(e['yr'].unique())})
    # 6. qualitative coverage
    qi = q[q['분석제외'] == 'N']
    R['qual_coverage'] = dict(rows=int(len(q)), included=int(len(qi)), excluded=q[q['분석제외'] == 'Y']['제외사유'].value_counts().to_dict(),
                              target_rows=int(qi['교육ID'].isin(T).sum()), target_resp=int(qi[qi['교육ID'].isin(T)]['비식별응답ID'].nunique()),
                              other_resp=int(qi[~qi['교육ID'].isin(T)]['비식별응답ID'].nunique()))
    R['notes'] = ins['notes']; R['target'] = tgt
    jdump(R, os.path.join(o.work, 'quant_results.json'))
    # ---- markdown summary for reading
    L = [f"# 정량 결과 요약 · 대상: {tgt['label']}", '', '## 공식 집계 재현']
    for c in chk: L.append(f"- {METRIC_KO.get(c['metric'], c['metric'])}: n {c['n']}/{c['official_n']}, 평균 {c['mean']:.3f}/{c['official_mean']:.3f}, 동일가중 {c['eqw']:.3f}/{c['official_eqw']:.3f} → {'일치' if c['ok'] else '불일치'}")
    L += ['', f"대상 원문항 재현: {R['target_item_check']['rows']}행, 불일치 {len(mism)}건", '', '## 연도별 (설문 행 | 추정 인원)']
    for m in MET:
        b = R['by']['연도'][m]
        L.append(f"- {METRIC_KO[m]}: " + ' · '.join(f"{k} {v['row']['mean']} (n={v['row']['n']}) | {v['person']['mean']} ({v['person']['units']}명) ≤3 {v['person']['le3']}" for k, v in b.items()))
    L += ['', '## 비교군 (추정 인원 기준)']
    for m in MET:
        b = R['by']['비교군'][m]
        L.append(f"- {METRIC_KO[m]}: " + ' · '.join(f"{k} {v['person']['mean']} ({v['person']['units']}명, ≤3 {v['person']['le3']})" for k, v in sorted(b.items())))
    L += ['', '## 대상 교육별']
    for it in per:
        L.append(f"### {it['id']} {it['name']} ({it['date']}, {it['mode']}, 대상 {it['target']}) 응답 {it['resp']}건/추정 {it['persons']}명 신분 {it['status']}")
        for m in MET:
            x = it['metrics'][m]
            if x['n']: L.append(f"  - {METRIC_KO[m]}: {x['mean']} n={x['n']} dist={x['dist']}")
        for i in it['items']: L.append(f"  - [문항 {i['qid']}] {i['text'][:60]}… {i['mean']} n={i['n']} dist={i['dist']}")
    L += ['', '## 대상 통합']
    for m, st in pooled.items():
        L.append(f"- {METRIC_KO[m]}: {st['row']['mean']} (n={st['row']['n']}, 동일가중 {st['eqw']}) ≤3 {st['row']['le3']} KW p={st.get('kruskal_p')} 신분별 " + ', '.join(f"{k} {v['mean']}({v['n']})" for k, v in st['by_status'].items()))
    L += ['', f"인지경로: {R['target_channels']}"]
    vm = R['version_mix']
    L += ['', '## 표준 설문 v2', f"- v2 문구 응답 {vm['v2_answers']}행, 교육 {len(vm['v2_educations'])}개 {vm['v2_educations'][:8]}",
          f"- v1·v2가 섞인 지표(추세는 조건부·참고만): {[METRIC_KO[m] for m in vm['mixed_metrics']] or '없음'}"]
    if R['bipolar']:
        b = R['bipolar']
        L.append(f"- 난이도(양극) 전체 적절 {b['overall']['fit']} · 쉬움 {b['overall']['easy']} · 어려움 {b['overall']['hard']} (n={b['overall']['n']}) | 대상 적절 {b['target']['fit']} · 쉬움 {b['target']['easy']} · 어려움 {b['target']['hard']} (n={b['target']['n']}, {b['target']['direction']})")
        for k, x in b['by_edu'].items(): L.append(f"  - {k}: 적절 {x['fit']} · 쉬움 {x['easy']} · 어려움 {x['hard']} (n={x['n']})")
    for item, pr in R['profile'].items():
        for scope, cats in pr['scopes'].items():
            L.append(f"- [{pr['label']}·{scope}] " + ' · '.join(f"{c} {v['n']}명" + (f" 전반 {v['overall_satisfaction']['mean']:.2f}" if 'overall_satisfaction' in v else '') + (f" 난이도 적절 {v[BIPOLAR]['fit']}" if BIPOLAR in v else '') for c, v in sorted(cats.items(), key=lambda kv: -kv[1]['n'])[:10]))
    L += ['', '## 이상 패턴']
    for b in bim:
        if b['flag']: L.append(f"- [양극단] {METRIC_KO[b['metric']]} {b['yr']}: 1점 {b['p1']} / 2점 {b['p2']}, 전반 5점 중 1점 {b['p1_among_overall5']}")
    for x in single:
        if x['target_hits']: L.append(f"- [단독 1점] {METRIC_KO[x['metric']]}: 대상 {len(x['target_hits'])}/{x['target_n']} {x['target_hits']} vs 그 외 {x['other_hits']}/{x['other_n']}")
    for x in lowc:
        if x['target']: L.append(f"- [저점 응답] {x['rid']} 저점 {x['low_items']}개, 주관식: {x['texts']}")
    L += ['', f"## 분할 단위: {R['split_units']}", f"## 주관식 범위: {R['qual_coverage']}"]
    open(os.path.join(o.work, 'quant_summary.md'), 'w', encoding='utf-8').write('\n'.join(L))
    print('\n'.join(L[:12])); print('… 전체는 quant_summary.md')


if __name__ == '__main__':
    main()
