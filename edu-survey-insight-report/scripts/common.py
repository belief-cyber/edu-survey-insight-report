"""Shared loaders and calculation rules for 학술정보교육 설문 데이터셋 (education-analysis-package-v1).

All analysis scripts import from here so that every run applies the same rules:
- valid numeric answer  = 분석포함=Y & 수치값 numeric & 비교가능성 in {A,B}
- integrated (respondent-level) metric = drop respondent×metric pairs with >1 source item
- year = 교육ID prefix (학년도), not the 연도 column
- split unit = same 교육군(ser) + same 교육시작일 + >1 교육ID + 운영방식 in SPLIT_MODES
- estimated person = within a split unit, same (신분|소속·전공 원문|인지경로) signature
  (only when at least 2 signature items are answered; standard survey v2 has no 소속·인지경로 in the
   post-survey, so v2 split responses stay one-row-one-respondent unless the package carries 응답자키)
- difficulty items are distribution-only: difficulty_appropriateness (legacy, meaning unverified) and
  difficulty_level (standard survey v2, bipolar 1 매우 쉬웠다 ~ 3 적절했다 ~ 5 매우 어려웠다)
"""
import json, os, re, sys
import numpy as np
import pandas as pd

# 5-point metrics. The first 7 are the legacy core (order kept: report/verify rely on difficulty at index 6).
# The rest became common or module items in standard survey v2 (2026-11-03); legacy data has them for a few educations only.
METRICS = ['overall_satisfaction', 'content_usefulness', 'delivery_method_satisfaction',
           'instructor_delivery', 'class_duration_satisfaction', 'goal_attainment',
           'difficulty_appropriateness',
           'instruction_composition', 'schedule_satisfaction', 'perceived_practical_help',
           'recommendation_intent', 'split_find_content', 'difficulty_level']
METRIC_KO = {'overall_satisfaction': '전반적 만족도', 'content_usefulness': '교육내용 유익성',
             'delivery_method_satisfaction': '진행방식·운영 방식 만족도', 'instructor_delivery': '강사 전달력',
             'class_duration_satisfaction': '교육시간(분량) 적절성', 'goal_attainment': '핵심역량·교육목표 달성 도움도',
             'difficulty_appropriateness': '난이도 적절성(구 척도)',
             'instruction_composition': '교육 구성 적절성', 'schedule_satisfaction': '교육 일정 편리성',
             'perceived_practical_help': '학업·연구 활용 가능성', 'recommendation_intent': '추천 의향',
             'split_find_content': '분할 구성의 탐색 용이성', 'difficulty_level': '난이도(양극 척도)'}
METRIC_SHORT = {'overall_satisfaction': '전반 만족', 'content_usefulness': '유익성', 'delivery_method_satisfaction': '운영방식',
                'instructor_delivery': '강사', 'class_duration_satisfaction': '교육시간', 'goal_attainment': '목표달성',
                'difficulty_appropriateness': '난이도(구)', 'instruction_composition': '교육구성', 'schedule_satisfaction': '일정',
                'perceived_practical_help': '활용', 'recommendation_intent': '추천', 'split_find_content': '분할탐색',
                'difficulty_level': '난이도'}
DIFFICULTY = ['difficulty_appropriateness', 'difficulty_level']   # distribution-only, never ranked by mean
BIPOLAR = 'difficulty_level'
LEVEL5_KO = ['매우 쉬움', '쉬움', '적절', '어려움', '매우 어려움']
# 신청 단계(또는 기존 사후 설문) 집단 구분 항목 — 평가 점수가 아니라 비교 기준
PROFILE_ITEMS = {'awareness_channel': '인지경로', 'participation_purpose': '참여 목적', 'prior_level': '사전 수준',
                 'research_stage': '연구 단계', 'thesis_type': '논문 종류'}
PRIOR_KO = {1: '1 처음', 2: '2 들어만 봄', 3: '3 몇 번 사용', 4: '4 자주 사용', 5: '5 남에게 알려 줄 정도'}
MODE_V2 = ['대면', 'ZOOM 실시간', 'ZOOM 실시간 + 녹화본 제공', '대면·ZOOM 혼합', '영상 제공']
SIG_ITEMS = ['respondent_status', 'affiliation_major', 'awareness_channel']
DEFAULT_SPLIT_MODES = ['영상 제공']
OPTIONAL_FILES = ['survey_items.csv', 'education_groups.csv', 'improvement_history.csv']
REQUIRED_FILES = ['manifest.json', 'educations.csv', 'participation.csv', 'survey_responses.csv',
                  'question_answers.csv', 'qualitative.csv', 'question_dictionary.csv',
                  'quantitative_summary.csv']


def read_csv(d, name, **kw):
    return pd.read_csv(os.path.join(d, name), encoding='utf-8-sig', **kw)


def series_of(eid):
    return re.sub(r'-\d+$', '', str(eid))


def compact(t):
    t = re.sub(r'\s+', '', str(t)).replace('ㆍ', '·').replace('‧', '·')
    return re.sub(r'^(q|문|sr|s|p)?\d+[.)]?', '', t, flags=re.I)


def load_items(d):
    """standard survey item bank (survey_items.csv, exported by the data hub from 2026-11). None if absent."""
    path = os.path.join(d, 'survey_items.csv')
    return read_csv(d, 'survey_items.csv', dtype=str) if os.path.exists(path) else None


def tag_version(a, items):
    """설문버전 per answer: 'v2' when 원문항 matches the v2 frame of the same 표준분석항목ID, else 'v1'."""
    if items is None or '일치패턴' not in items:
        return pd.Series('v1', index=a.index)
    pats = items.dropna(subset=['일치패턴']).groupby('표준분석항목ID')['일치패턴'].apply(list).to_dict()
    cache = {}
    def f(var, text):
        k = (var, text)
        if k not in cache:
            cache[k] = 'v2' if any(re.search(p, compact(text)) for p in pats.get(var, [])) else 'v1'
        return cache[k]
    return pd.Series([f(v, t) for v, t in zip(a['표준분석항목ID'], a['원문항'])], index=a.index)


def norm_mode(t):
    """운영방식 → standard survey v2 Q7 vocabulary (legacy labels mapped; unknown kept)."""
    t = str(t).strip()
    if t in ('nan', '', 'None'): return '미상'
    if t in MODE_V2: return t
    if '혼합' in t: return '대면·ZOOM 혼합'
    if '녹화' in t: return 'ZOOM 실시간 + 녹화본 제공'
    if '실시간' in t or 'zoom' in t.lower() or t == '비대면': return 'ZOOM 실시간'
    if '영상' in t: return '영상 제공'
    if '대면' in t: return '대면'
    return t


def load(d, split_modes=None):
    """Return dict of dataframes with derived columns. d = unzipped package dir."""
    split_modes = split_modes or DEFAULT_SPLIT_MODES
    e = read_csv(d, 'educations.csv')
    p = read_csv(d, 'participation.csv')
    s = read_csv(d, 'survey_responses.csv')
    a = read_csv(d, 'question_answers.csv', dtype=str)
    q = read_csv(d, 'qualitative.csv')
    qs = read_csv(d, 'quantitative_summary.csv')
    a['val'] = pd.to_numeric(a['수치값'], errors='coerce')
    items = load_items(d)
    a['설문버전'] = tag_version(a, items)
    e['yr'] = e['교육ID'].str[:4]
    e['ser'] = e['교육ID'].map(series_of)
    e['serkey'] = e['ser'].str.split('-', n=1).str[1]
    e['date'] = e['교육시작일'].astype(str).str[:10].replace({'nan': '', 'NaT': ''})
    e['unit'] = e['ser'] + '@' + e['date']
    cnt = e.groupby('unit')['교육ID'].transform('nunique')
    e['split'] = (cnt > 1) & e['운영방식'].isin(split_modes) & (e['date'] != '')
    e['mode2'] = e['운영방식'].map(norm_mode)
    e = e.merge(p, on='교육ID', how='left')
    a = a.merge(e[['교육ID', 'yr', 'unit', 'split', '교육유형', '운영방식', 'mode2', '교육대상']], on='교육ID', how='left')
    a = a.merge(s[['비식별응답ID', '응답자신분']], on='비식별응답ID', how='left')
    # estimated persons
    sig = a[a['표준분석항목ID'].isin(SIG_ITEMS)].pivot_table(
        index=['비식별응답ID', 'unit', 'split'], columns='표준분석항목ID', values='원본응답값', aggfunc='first').reset_index()
    for c in SIG_ITEMS:
        if c not in sig: sig[c] = ''
    sig['key'] = sig['unit'].astype(str) + '|' + sig[SIG_ITEMS].astype(object).where(sig[SIG_ITEMS].notna(), 'nan').astype(str).agg('|'.join, axis=1)
    enough = sig[SIG_ITEMS].notna().sum(axis=1) >= 2   # status alone would merge everyone in a unit
    sig['person'] = np.where(sig['split'] & enough, sig['key'], sig['비식별응답ID'])
    if '응답자키' in s.columns:   # optional de-identified respondent key (not exported yet)
        rk = s.set_index('비식별응답ID')['응답자키'].dropna().astype(str)
        sig['person'] = [f"{u}|{rk[r]}" if r in rk.index else p for r, u, p in zip(sig['비식별응답ID'], sig['unit'], sig['person'])]
    pmap = dict(zip(sig['비식별응답ID'], sig['person']))
    s['person'] = s['비식별응답ID'].map(pmap).fillna(s['비식별응답ID'])
    a['person'] = a['비식별응답ID'].map(pmap).fillna(a['비식별응답ID'])
    return dict(e=e, p=p, s=s, a=a, q=q, qs=qs, items=items)


def valid(a):
    return a[(a['분석포함'] == 'Y') & a['val'].notna() & a['비교가능성'].isin(['A', 'B'])]


def integrated(a, metric):
    v = valid(a)
    v = v[v['표준분석항목ID'] == metric]
    k = v.groupby('비식별응답ID')['원본문항ID'].transform('nunique')
    return v[k == 1]


def agg_values(df, basis='row'):
    """df: rows with val (+ person). basis row|person. Returns stats dict."""
    if df.empty:
        return dict(n=0, units=0, mean=None, sd=None, top=None, le3=None, dist=[0] * 5)
    if basis == 'person':
        w = 1 / df.groupby('person')['val'].transform('size')
        units = df['person'].nunique()
        mean = float((df['val'] * w).sum() / units)
    else:
        w = pd.Series(1.0, index=df.index)
        units = len(df)
        mean = float(df['val'].mean())
    dist = [float(w[df['val'] == k].sum()) for k in range(1, 6)]
    return dict(n=int(len(df)), units=int(units), mean=round(mean, 4),
                sd=round(float(df['val'].std()), 4) if len(df) > 1 else None,
                top=round(dist[4] / units, 4), le3=round(sum(dist[:3]) / units, 4),
                dist=[round(x, 3) for x in dist])


def bipolar(df, basis='row'):
    """Bipolar difficulty summary: share easy (1-2) / appropriate (3) / hard (4-5)."""
    st = agg_values(df, basis)
    if not st['n']:
        return dict(n=0, units=0, easy=None, fit=None, hard=None, direction=None, dist=st['dist'])
    d, u = st['dist'], st['units']
    easy, fit, hard = (d[0] + d[1]) / u, d[2] / u, (d[3] + d[4]) / u
    return dict(n=st['n'], units=u, easy=round(easy, 4), fit=round(fit, 4), hard=round(hard, 4),
                direction='쉬움 쪽' if easy > hard else '어려움 쪽' if hard > easy else '균형', dist=d)


def profile_values(a, item):
    """Respondent → category label for a profile (group-by) item. Multi-select answers split on comma."""
    x = a[a['표준분석항목ID'] == item][['비식별응답ID', '원본응답값', 'val']].dropna(subset=['원본응답값'])
    if x.empty: return pd.DataFrame(columns=['비식별응답ID', 'cat'])
    if item == 'awareness_channel':
        x['cat'] = x['원본응답값'].map(norm_channel)
    elif item == 'prior_level':
        x['cat'] = x['val'].map(lambda v: PRIOR_KO.get(int(v)) if pd.notna(v) else None).fillna(x['원본응답값'].astype(str))
    else:
        x['cat'] = x['원본응답값'].astype(str).str.split(r'\s*[,/]\s*') if item == 'thesis_type' else x['원본응답값'].astype(str)
        x = x.explode('cat')
    return x[['비식별응답ID', 'cat']].drop_duplicates()


def edu_equal(df):
    if df.empty: return None
    return round(float(df.groupby('교육ID')['val'].mean().mean()), 4)


def mask_names(text, extra=None):
    """Mask '홍길동박사님/사서님/강사님/교수님/선생님' style personal names (2-3 syllable + title)."""
    t = str(text).replace('&quot;', '"').replace('&#039;', "'").replace('&amp;', '&')
    stop = {'교수', '강사', '선생', '박사', '사서', '담당자', '진행', '특강', '오늘', '그러나', '대해서', '하신', '주신',
            '해주신', '젊은', '파트타임', '되었고', '업시간에', '짧아서', '낯설어', '있었는데'}
    surnames = set('김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민진나지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용예봉경')
    def rep(m):
        name = m.group(1)
        if name in stop or name[0] not in surnames:
            return m.group(0)
        return '○○○' + m.group(2)
    t = re.sub(r'(?<![가-힣])([가-힣]{3})\s?(박사님|사서님|강사님|교수님|선생님)', rep, t)
    for n in (extra or []):
        t = t.replace(n, '○○○')
    return t


def cmp_group(row, tgt_ids, kws, tyears):
    """Comparison group label for an education row (needs 교육ID, 교육명, serkey, yr)."""
    if row['교육ID'] in tgt_ids: return '① 대상 교육'
    name = f"{row['교육명']} {row['serkey']}"
    if kws and any(k.lower() in name.lower() for k in kws):
        return f"② 유사 주제 {row['yr']}" if row['yr'] in tyears else f"③ 유사 주제 {row['yr']}"
    return f"④ 그 외 {row['yr']}"


CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩'


def cmp_labels(e, tgt_ids, kws, tyears):
    """Series of numbered comparison-group labels: target, similar (same year), similar (other years), others by year."""
    def base(r):
        if r['교육ID'] in tgt_ids: return (0, '', '대상 교육')
        name = f"{r['교육명']} {r['serkey']}"
        if kws and any(k.lower() in name.lower() for k in kws):
            return (1 if r['yr'] in tyears else 2, r['yr'], f"유사 주제 {r['yr']}")
        return (3, r['yr'], f"그 외 {r['yr']}")
    b = e.apply(base, axis=1)
    order = sorted(set(b))
    num = {k: CIRCLED[i] + ' ' + k[2] for i, k in enumerate(order)}
    return b.map(num)


def norm_channel(t):
    t = str(t)
    rules = [('hy-lu-e', '하이루이·비교과 시스템'), ('포스터', '오프라인 홍보물'), ('메일', '학술정보관 메일'), ('홈페이지', '학술정보관 홈페이지'), ('헤이영', '헤이영 알림'), ('문자', '문자 안내'),
             ('인스타', 'SNS'), ('SNS', 'SNS'), ('추천', '지인·교수 추천'), ('지인', '지인·교수 추천'), ('친구', '지인·교수 추천'),
             ('현수막', '오프라인 홍보물'), ('홍보물', '오프라인 홍보물'), ('하이루이', '하이루이·비교과 시스템'), ('HYLUE', '하이루이·비교과 시스템'),
             ('hylu', '하이루이·비교과 시스템'), ('비교과', '하이루이·비교과 시스템'), ('단톡', '학과 안내'), ('학과', '학과 안내')]
    if t in ('nan', '', 'None'): return '결측'
    for k, v in rules:
        if k.lower() in t.lower(): return v
    return '기타'


def jdump(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=lambda x: None if (isinstance(x, float) and np.isnan(x)) else (x.item() if hasattr(x, 'item') else str(x)))


def jload(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)
