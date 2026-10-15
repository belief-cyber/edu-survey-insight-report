#!/usr/bin/env python3
"""Step 5b. Validate report_content.json before building.

usage: python validate_content.py --work W --content W/report_content.json
Errors (exit 1): missing sections/fields, TODO markers, unknown evidence IDs/codes,
                 quoted text (“…”) that does not appear in the cited originals, invalid tiers, numeric priority scores.
Warnings: numbers in the text that cannot be found in quant/qual results (check them by hand).
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

HERE = os.path.dirname(os.path.abspath(__file__))
REQ = {
    'title': str, 'purpose': str, 'summary': dict, 'data_notes': list, 'explorer_interpretation': dict, 'target_lead': str,
    'insights': list, 'dt_scope': str, 'issue': dict, 'persona_note': str, 'personas': list, 'empathy': dict,
    'pain_points': list, 'pain_relation': str, 'problem_statements': list, 'hmw': list, 'recommendations': list, 'limitations': list}
FIELDS = {'insights': ['title', 'tag', 'scope', 'obs', 'quant', 'qual', 'interp', 'implication'],
          'pain_points': ['title', 'type', 'context', 'strength', 'strength_label'],
          'problem_statements': ['scope', 'situation', 'need', 'because'],
          'hmw': ['q', 'basis'],
          'recommendations': ['id', 'tier', 'title', 'who', 'need', 'evidence', 'direction', 'ideas', 'effect', 'constraints', 'evaluation'],
          'personas': ['name', 'desc']}


def walk(x, path=''):
    if isinstance(x, dict):
        for k, v in x.items(): yield from walk(v, f'{path}.{k}')
    elif isinstance(x, list):
        for i, v in enumerate(x): yield from walk(v, f'{path}[{i}]')
    else:
        yield path, x


def flat_numbers(obj, acc):
    if isinstance(obj, dict):
        for v in obj.values(): flat_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj: flat_numbers(v, acc)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        acc.add(round(float(obj), 2)); acc.add(round(float(obj), 1)); acc.add(round(float(obj) * 100, 1)); acc.add(round(float(obj) * 100))
        acc.add(round(float(obj), 3))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--work', required=True); ap.add_argument('--content', required=True)
    ap.add_argument('--codebook', default=os.path.join(HERE, '..', 'assets', 'codebook.json'))
    o = ap.parse_args()
    C = jload(o.content); QF = jload(os.path.join(o.work, 'qual_final.json')); QR = jload(os.path.join(o.work, 'quant_results.json'))
    ins = jload(os.path.join(o.work, 'inspect.json')); cb = jload(o.codebook)
    s = read_csv(ins['pkg_dir'], 'survey_responses.csv'); e = read_csv(ins['pkg_dir'], 'educations.csv')
    qtext = {r['id']: r['t'] for r in QF['rows']}; rids = set(s['비식별응답ID']); eids = set(e['교육ID']); codes = {c['code'] for c in cb['codes']}
    err, warn = [], []
    for k, t in REQ.items():
        if k not in C: err.append(f'필수 항목 없음: {k}')
        elif not isinstance(C[k], t): err.append(f'{k} 형식 오류({t.__name__} 필요)')
    for sec, fs in FIELDS.items():
        for i, it in enumerate(C.get(sec, []) or []):
            for f in fs:
                if f not in it or it[f] in ('', None): err.append(f'{sec}[{i}].{f} 비어 있음')
    if C.get('summary'):
        for f in ['question', 'scope', 'rows']:
            if f not in C['summary']: err.append(f'summary.{f} 없음')
    for p, v in walk(C):
        if isinstance(v, str) and re.search(r'TODO|TBD|채워 넣|＿＿', v): err.append(f'미작성 표시 남음: {p}')
        if re.search(r'\.(score|priority_score|점수)$', p): err.append(f'수치 우선순위 필드 금지: {p}')
    # evidence
    for p, v in walk(C):
        if re.search(r'\.ev\.q\[\d+\]$', p) and v not in qtext: err.append(f'없는 주관식ID: {v} ({p})')
        if re.search(r'\.ev\.r\[\d+\]$', p) and v not in rids: err.append(f'없는 응답ID: {v} ({p})')
        if re.search(r'\.ev\.edu\[\d+\]$', p) and v not in eids: err.append(f'없는 교육ID: {v} ({p})')
        if re.search(r'\.ev\.theme$', p) and v not in codes: err.append(f'없는 코드: {v} ({p})')
        if re.search(r'sensitivity\.exclude\[\d+\]$', p) and v not in rids: err.append(f'민감도 제외 ID 없음: {v}')
    for r in C.get('recommendations', []):
        if r.get('tier') not in ('t0', 't1', 't2', 't3'): err.append(f"권고 {r.get('id')} tier 값 오류(t0 유지/t1 우선/t2 검토/t3 탐색)")
    for i, h in enumerate(C.get('hmw', [])):
        if str(h.get('q', '')).startswith('우리가 어떻게'): warn.append(f'hmw[{i}].q: "우리가 어떻게 하면"은 템플릿이 붙이므로 빼세요')
    # quotes must exist in cited originals
    def check_quotes(text, ev, where, strict):
        cited = ' '.join(qtext.get(i, '') for i in (ev or {}).get('q', [])) or ' '.join(qtext.values())
        for qt in re.findall(r'“([^”]+)”', text or ''):
            parts = [x.strip(' .,') for x in re.split(r'…|\.\.\.', qt) if len(x.strip(' .,')) >= 4]
            miss = [x for x in parts if re.sub(r'\s+', '', x) not in re.sub(r'\s+', '', cited)]
            if miss: (err if strict else warn).append(f'{where}: 인용문이 원문에 없음 → “{qt[:40]}”')
    for k in ['says', 'feels']:
        for i, it in enumerate((C.get('empathy') or {}).get(k, [])):
            check_quotes(it.get('text'), it.get('ev'), f'empathy.{k}[{i}]', strict=(k == 'says'))
            if k == 'says' and not (it.get('ev') or {}).get('q'): err.append(f'empathy.says[{i}]: 원문 근거(ev.q) 필요')
    for p, v in walk(C):
        if isinstance(v, str) and '“' in v and '.empathy.' not in p: check_quotes(v, None, p, strict=False)
    # numbers cross-check
    acc = set(); flat_numbers(QR, acc)
    for t in QF['target']['themes'].values(): acc.update([t['resp'], t['mentions'], t['edus'], t['pct']])
    for t in QF['other']['themes'].values(): acc.update([t['resp'], t['mentions'], t['edus'], t['pct']])
    for p, v in walk(C):
        if not isinstance(v, str): continue
        for num in re.findall(r'(?<![\d.\-])(\d\.\d{2,3})(?![\d])', v):
            if round(float(num), len(num.split('.')[1])) not in acc and round(float(num), 2) not in acc:
                warn.append(f'{p}: {num} — 정량 결과에서 같은 값을 찾지 못함(직접 확인)')
    for x in err: print('ERROR', x)
    for x in warn[:60]: print('WARN ', x)
    print(f'콘텐츠 검증: 오류 {len(err)} · 경고 {len(warn)}')
    sys.exit(1 if err else 0)


if __name__ == '__main__':
    main()
