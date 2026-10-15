#!/usr/bin/env python3
"""Step 1. Unpack + validate an analysis package and print an overview.

usage: python inspect_package.py <package.zip|dir> --work <workdir>
writes <workdir>/pkg/ (unzipped, if zip) and <workdir>/inspect.json
"""
import argparse, hashlib, os, sys, zipfile
sys.path.insert(0, os.path.dirname(__file__))
from common import *


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('package')
    ap.add_argument('--work', required=True)
    ap.add_argument('--split-modes', default=','.join(DEFAULT_SPLIT_MODES))
    a_ = ap.parse_args()
    os.makedirs(a_.work, exist_ok=True)
    d = a_.package
    if zipfile.is_zipfile(d):
        out = os.path.join(a_.work, 'pkg')
        os.makedirs(out, exist_ok=True)
        with zipfile.ZipFile(d) as z:
            for n in z.namelist():
                if n.startswith('/') or '..' in n: sys.exit('unsafe path in zip: ' + n)
            z.extractall(out)
        # package may be nested in one folder
        subs = [x for x in os.listdir(out) if os.path.isdir(os.path.join(out, x))]
        d = out if os.path.exists(os.path.join(out, 'manifest.json')) or not subs else os.path.join(out, subs[0])
    missing = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(d, f))]
    if missing:
        sys.exit('필수 파일 누락: ' + ', '.join(missing))
    man = jload(os.path.join(d, 'manifest.json'))
    checks = []
    for fn, info in man.get('files', {}).items():
        fp = os.path.join(d, fn)
        if not os.path.exists(fp):
            checks.append((fn, 'MISSING')); continue
        h = hashlib.sha256(open(fp, 'rb').read()).hexdigest()
        checks.append((fn, 'OK' if h == info.get('sha256') else 'SHA_MISMATCH'))
    D = load(d, a_.split_modes.split(','))
    e, s, a, q = D['e'], D['s'], D['a'], D['q']
    notes = []
    nos = e[e['설문응답수'].fillna(0) == 0]
    if len(nos): notes.append(dict(kind='survey_missing', ids=nos['교육ID'].tolist(), text='설문 응답 0건(누락/제외) 교육'))
    mism = e[e['연도'].astype(str) != e['yr']]
    if len(mism): notes.append(dict(kind='year_mismatch', ids=mism['교육ID'].tolist(), text='교육ID 연도와 연도 열 불일치(교육ID=학년도 기준 사용)'))
    gaps = e[e['운영방식'].isna() | (e['date'] == '') | e['교육대상'].isna()]
    if len(gaps): notes.append(dict(kind='metadata_gap', ids=gaps['교육ID'].tolist(), text='운영방식·일자·대상 공란'))
    rr = e[e['응답률계산가능'] == 'Y']
    notes.append(dict(kind='response_rate', ids=[], text=f"응답률 산출 가능 교육 {len(rr)}개, 합산 {rr['설문응답수'].sum()/rr['응답률분모'].sum():.1%}" if len(rr) else '응답률 산출 가능 교육 없음'))
    sp = e[e['split']]
    if len(sp):
        n_rows = int(s[s['교육ID'].isin(sp['교육ID'])].shape[0]); n_p = s[s['교육ID'].isin(sp['교육ID'])]['person'].nunique()
        notes.append(dict(kind='split_units', ids=sp['교육ID'].tolist(), text=f"분할 운영 단위 {sp['unit'].nunique()}개(교육ID {len(sp)}개): 응답 {n_rows}건 → 추정 {n_p}명"))
    imp = os.path.join(d, 'improvement_history.csv')
    if os.path.exists(imp):
        notes.append(dict(kind='improvement_history', ids=[], text=f"개선 이력 {len(read_csv(d, 'improvement_history.csv'))}행"))
    notes.append(dict(kind='coding_status', ids=[], text='주관식 코딩 상태: ' + ', '.join(f'{k} {v}' for k, v in q['코딩상태'].value_counts().items())))
    ser = e.groupby(['serkey']).agg(n=('교육ID', 'size'), names=('교육명', lambda x: ' / '.join(sorted(set(map(str, x)))[:3])),
                                    years=('yr', lambda x: ','.join(sorted(set(x)))), resp=('설문응답수', 'sum')).reset_index()
    res = dict(pkg_dir=os.path.abspath(d), manifest=dict((k, man.get(k)) for k in ['package_version', 'export_id', 'dataset_version_id', 'analysis_run_id', 'qualitative_run_id', 'created_at', 'counts', 'validation']),
               sha_checks=checks, notes=notes, series=ser.to_dict('records'),
               split_modes=a_.split_modes.split(','))
    jdump(res, os.path.join(a_.work, 'inspect.json'))
    print('패키지:', man.get('package_version'), '| 데이터:', man.get('dataset_version_id'))
    print('SHA 검사:', ', '.join(f'{f}={c}' for f, c in checks))
    print('교육', len(e), '| 응답', len(s), '| 문항응답', len(a), '| 주관식', len(q))
    for n in notes: print('-', n['text'], (n['ids'][:6] if n['ids'] else ''))
    print('\n교육군 목록(serkey | 교육 수 | 연도 | 응답 | 교육명 예):')
    for r in ser.itertuples(): print(f'  {r.serkey} | {r.n} | {r.years} | {int(r.resp)} | {r.names}')


if __name__ == '__main__':
    main()
