#!/usr/bin/env python3
"""Step 6. Build the standalone interactive HTML report.

usage: python build_report.py --work W --content W/report_content.json --out W/report.html [--allow-draft]
Embeds: respondent-level metrics, education metadata, coded qualitative rows, codebook labels,
official summary rows and the author-written content JSON into assets/report_template.html.
The template recomputes every statistic in the browser; content text is shown as fixed-scope interpretation.
"""
import argparse, datetime, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True); ap.add_argument('--content', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--template', default=os.path.join(HERE, '..', 'assets', 'report_template.html'))
    ap.add_argument('--codebook', default=os.path.join(HERE, '..', 'assets', 'codebook.json'))
    ap.add_argument('--allow-draft', action='store_true', help='skip content validation errors (test renders only)')
    o = ap.parse_args()
    v = subprocess.run([sys.executable, os.path.join(HERE, 'validate_content.py'), '--work', o.work, '--content', o.content], capture_output=True, text=True)
    print(v.stdout.strip())
    if v.returncode != 0 and not o.allow_draft:
        sys.exit('콘텐츠 검증 실패 — 오류를 고친 뒤 다시 빌드하세요. (시험 렌더링만 필요하면 --allow-draft)')
    ins = jload(os.path.join(o.work, 'inspect.json')); tgt = jload(os.path.join(o.work, 'target.json'))
    QR = jload(os.path.join(o.work, 'quant_results.json')); QF = jload(os.path.join(o.work, 'qual_final.json'))
    content = jload(o.content); cb = jload(o.codebook)
    D = load(ins['pkg_dir'], ins['split_modes']); e, s, a = D['e'], D['s'], D['a']
    T = set(tgt['survey_ids'])
    e['cmp'] = cmp_labels(e, T, tgt['similar_keywords'], tgt['years'])
    sername = e.groupby('ser')['교육명'].first().astype(str).str.replace(r'-\d+$', '', regex=True).to_dict()
    edus = []
    for _, r in e.iterrows():
        nn = lambda x: None if pd.isna(x) else int(x)
        edus.append(dict(id=r['교육ID'], name=str(r['교육명']), y=r['yr'], type=r['교육유형'] if isinstance(r['교육유형'], str) else '미상',
                         mode=r['운영방식'] if isinstance(r['운영방식'], str) else '미상', target=r['교육대상'] if isinstance(r['교육대상'], str) else '미상',
                         date=r['date'], ser=r['ser'], serName=f"{sername.get(r['ser'], r['ser'])} ({r['yr']})" if e[e['ser'] == r['ser']]['yr'].nunique() == 1 else sername.get(r['ser']),
                         unit=r['unit'], split=bool(r['split']), app=nn(r['신청자수_기준표']), part=nn(r['참여자수_기준표']),
                         resp=int(r['설문응답수']) if not pd.isna(r['설문응답수']) else 0,
                         rr=None if r['응답률계산가능'] != 'Y' else round(float(r['응답률']), 4), isT=r['교육ID'] in T, cmp=r['cmp']))
    eidx = {d['id']: i for i, d in enumerate(edus)}
    vals = {m: integrated(a, m).set_index('비식별응답ID')['val'].to_dict() for m in METRICS}
    ch = a[a['표준분석항목ID'] == 'awareness_channel'].drop_duplicates('비식별응답ID').set_index('비식별응답ID')['원본응답값'].to_dict()
    pid = {}; resp = []
    for _, r in s.iterrows():
        rid = r['비식별응답ID']; pid.setdefault(r['person'], len(pid))
        resp.append([rid, eidx[r['교육ID']], r['응답자신분'] if isinstance(r['응답자신분'], str) else '미분류', pid[r['person']], norm_channel(ch.get(rid))] +
                    [None if pd.isna(vals[m].get(rid, np.nan)) else int(vals[m][rid]) for m in METRICS])
    items = [dict(edu=it['id'], **{k: x[k] for k in ['metric', 'qid', 'text', 'n', 'mean', 'dist']}) for it in QR['target_edus'] for x in it['items']]
    for m in {x['metric'] for x in items}:
        grp = [x for x in items if x['metric'] == m]
        pre = os.path.commonprefix([x['text'] for x in grp]) if len(grp) > 1 else ''
        for x in grp:
            txt = (x['text'][len(pre):] if len(pre) >= 12 else x['text']) or x['text']
            mm = re.search(r'\[[^\]]+\].*', txt)
            x['text'] = (mm.group(0) if mm else txt).strip() or x['text']
    multi_q = {x['qid'] for x in items}
    tv = valid(a[a['교육ID'].isin(T)])
    item_scores = {}
    for _, r in tv[tv['원본문항ID'].isin(multi_q)].iterrows():
        item_scores.setdefault(r['비식별응답ID'], {})[r['원본문항ID']] = int(r['val'])
    qual = [dict(id=r['id'], rid=r['rid'], e=eidx.get(r['edu']), q=r['q'], t=r['t'], c=r['codes'], g=r['g'], st=r['st']) for r in QF['rows']]
    man = ins['manifest']; val = man.get('validation') or {}
    groups = sorted(e[e['설문응답수'].fillna(0) > 0]['cmp'].unique())
    data = dict(meta=dict(package=man.get('package_version'), export=man.get('export_id'), dataset=man.get('dataset_version_id'),
                          quant=man.get('analysis_run_id'), qual=man.get('qualitative_run_id'), created=man.get('created_at'), counts=man.get('counts'),
                          validation=f"passed={val.get('passed')} · 직접식별자 검사 {((man.get('privacy') or {}).get('direct_identifier_scan')) or '정보 없음'}"),
                metrics=METRICS, metricKo=METRIC_KO,
                metricShort={'overall_satisfaction': '전반 만족', 'content_usefulness': '유익성', 'delivery_method_satisfaction': '진행방식', 'instructor_delivery': '강사',
                             'class_duration_satisfaction': '교육시간', 'goal_attainment': '핵심역량', 'difficulty_appropriateness': '난이도'},
                edus=edus, resp=resp, qual=qual, targetItems=items, itemScores=item_scores,
                codeLabel={c['code']: c['label'] for c in cb['codes']}, codePol={c['code']: c['polarity'] for c in cb['codes']},
                official=[dict(metric=c['metric'], n=c['official_n'], mean=c['official_mean'], eqw=c['official_eqw']) for c in QR['official_check']],
                target=dict(label=tgt['label'], ids=tgt['survey_ids']),
                cmpNote='비교군: ' + ' · '.join(groups) + (f" (유사 주제 키워드: {', '.join(tgt['similar_keywords'])})" if tgt['similar_keywords'] else '') + '. 운영방식과 대상이 서로 달라 직접 우열 비교가 아닌 참고용입니다.',
                codingNote=f"패키지 코딩 상태 그대로 사용하지 않음 → 포함 원문 {len(qual)}행 전수 검토, 수작업 수정 {QF['n_overrides']}건 ({QF['codebook']})",
                generated=datetime.date.today().isoformat())
    js = lambda x: json.dumps(x, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = open(o.template, encoding='utf-8').read().replace('/*__DATA__*/', js(data)).replace('/*__CONTENT__*/', js(content))
    os.makedirs(os.path.dirname(os.path.abspath(o.out)), exist_ok=True)
    open(o.out, 'w', encoding='utf-8').write(html)
    print(f'보고서 생성: {o.out} ({len(html)//1024}KB, 응답 {len(resp)}, 주관식 {len(qual)}, 대상 {len(T)}개 교육)')


if __name__ == '__main__':
    main()
