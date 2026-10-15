#!/usr/bin/env python3
"""Step 5a. Create a report_content.json draft.

usage: python content_skeleton.py --work W [--out W/report_content.json]
Fills fact-only parts automatically (data notes, per-education cards, anomaly candidates, problem/HMW slots)
and leaves "TODO:" markers where analyst interpretation is required. validate_content.py fails while any TODO remains.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

TODO = 'TODO: '


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--work', required=True); ap.add_argument('--out', default='')
    o = ap.parse_args()
    out = o.out or os.path.join(o.work, 'report_content.json')
    if os.path.exists(out): sys.exit(f'{out} 이미 있음 — 덮어쓰지 않습니다.')
    QR = jload(os.path.join(o.work, 'quant_results.json')); QF = jload(os.path.join(o.work, 'qual_final.json'))
    tgt = QR['target']; label = tgt['label']
    notes = []
    for n in QR['notes']:
        badge = {'survey_missing': 'fix', 'year_mismatch': 'fix', 'metadata_gap': 'fix', 'response_rate': 'warn', 'split_units': 'fix',
                 'improvement_history': 'fix', 'coding_status': 'fix'}.get(n['kind'], 'fix')
        notes.append(dict(badge=badge, title={'survey_missing': '설문 누락 교육', 'year_mismatch': '연도 표기', 'metadata_gap': '메타데이터 공란',
                                              'response_rate': '응답률', 'split_units': '분할 운영 단위', 'improvement_history': '개선 이력',
                                              'coding_status': '주관식 코딩 상태'}.get(n['kind'], n['kind']),
                          text=n['text'] + (f" ({', '.join(n['ids'][:4])}{' 외' if len(n['ids']) > 4 else ''})" if n['ids'] else '')))
    for b in QR['bimodal_check']:
        if b['flag']:
            notes.append(dict(badge='warn', title=f"{METRIC_KO[b['metric']]} 양극단 분포({b['yr']})",
                              text=f"1점 {b['p1']:.1%}, 2점 {b['p2']:.1%}, 전반 만족 5점 응답자 중 1점 {b['p1_among_overall5'] or 0:.1%}. 척도 방향·선택지 구성 확인 전까지 평균 해석을 제한합니다."))
    cards = {}
    for it in QR['target_edus']:
        ms = {k: v for k, v in it['metrics'].items() if v['n'] and k != 'difficulty_appropriateness'}
        low = min(ms.items(), key=lambda kv: kv[1]['mean']) if ms else None
        c = [f"응답 {it['resp']}건(추정 {it['persons']}명) · " + ' · '.join(f'{k} {v}' for k, v in it['status'].items())]
        if low: c.append(f"가장 낮은 지표: {METRIC_KO[low[0]]} {low[1]['mean']:.2f}(n={low[1]['n']})")
        if it['target'] and it['status'] and it['target'] not in it['status']:
            c.append(f"교육대상({it['target']})과 응답자 구성 불일치 확인")
        c.append(TODO + '이 교육에서만 나타난 특징(주관식·이상 응답)을 1~2개 추가')
        cards[it['id']] = c
    anomalies = []
    for x in QR['single_item_extreme']:
        if x['target_hits']:
            anomalies.append(dict(title=f"{METRIC_KO[x['metric']]} 단독 1점", text=f"다른 지표가 모두 5점인데 이 지표만 1점인 응답 {len(x['target_hits'])}명/{x['target_n']} (그 외 교육 {x['other_hits']}/{x['other_n']}). " + TODO + '해석 보류 여부를 쓰세요',
                                  ev=dict(r=x['target_hits'][:10])))
    for x in QR['low_score_respondents']:
        if x['target']:
            anomalies.append(dict(title=f"저점 응답 {x['rid'][-8:]}", text=f"저점 지표 {x['low_items']}개. 주관식: {x['texts'] or '없음'}. " + TODO + '척도 역방향 의심인지 실제 불만인지 원문과 대조',
                                  ev=dict(r=[x['rid']])))
    C = dict(
        doc_title=f'{label} 통합분석 보고서', header_sub='학술정보교육 설문 정량·정성 통합분석',
        title=f'{"~".join(sorted({r[:4] for r in QR["by"]["연도"]["overall_satisfaction"].keys()}))} 학술정보교육 통합분석 보고서',
        subtitle=f'분석 대상: {label} {len(tgt["survey_ids"])}개 교육', purpose=TODO + (tgt.get('purpose') or '분석 목적 1~2문장'),
        summary=dict(question=TODO + '이번 분석이 답할 질문(예: 다음 교육에서 무엇을 유지·개선할 것인가?)', scope=f'전체 교육 + {label}',
                     rows=[dict(k='유지·강화', items=[dict(text=TODO + '근거 수치와 함께', ev={})]),
                           dict(k='우선 개선', items=[dict(text=TODO, ev={})]),
                           dict(k='검토·탐색', items=[dict(text=TODO, ev={})])]),
        data_lead='교육ID를 기준키로 사용했으며 연도는 교육ID(학년도) 기준입니다. 분할 운영 단위(동일 교육군·동일 일자·영상 제공)는 신분·소속·인지경로가 같은 응답을 한 사람으로 추정한 **추정 인원** 기준을 함께 제공합니다.',
        data_notes=notes,
        explorer_interpretation=dict(scope='전체 교육 · 전체 응답자', items=[TODO + '유형·운영방식·신분이 겹쳐 있음 등 탐색 결과 해석 3~5개']),
        difficulty_warning='난이도 문항은 척도 방향·선택지 구성이 검증되지 않았습니다. 평균을 비교하거나 높낮이로 해석하지 말고 분포만 참고하세요.',
        target_lead=TODO + f"{label} 개요: 교육 수, 응답 수, 교육 간 차이 검정 결과(Kruskal-Wallis p) 요약",
        target_default_metric=0, sensitivity=dict(exclude=[], label='', reason=''),
        target_cards=cards, anomalies=anomalies, compare_note='',
        insights=[dict(title=TODO, tag='대상 특화|전체 공통|근거 일치|해석 제한', scope=TODO, obs=TODO, quant=TODO, qual=TODO, interp=TODO, implication=TODO, ev={})],
        dt_scope=f"범위: {label} 응답 · 주관식 {QF['target']['base_resp']}명 {QF['target']['base_rows']}행",
        issue={k: dict(text=TODO, kind='fact', ev={}) for k in ['user', 'need', 'goal', 'problem', 'action']},
        persona_note=TODO + '신분만으로 니즈가 다르다고 단정하지 말 것. 표본·근거 한계를 쓰고, 근거가 없으면 personas를 비워 둔다.',
        personas=[], empathy=dict(center=f'{label} 참여자', says=[], thinks=[], does=[], feels=[], pains=TODO, gains=TODO, needs=TODO),
        pain_points=[], pain_relation=TODO, problem_statements=[dict(scope=label, situation=TODO, need=TODO, because=TODO)],
        hmw=[], recommendations=[], limitations=[TODO + '표본 크기, 추정 인원의 한계, 코딩 신뢰도, 척도 확인 필요 사항 등'])
    jdump(C, out)
    print(f'초안 생성: {out} — TODO를 모두 채운 뒤 validate_content.py를 실행하세요.')


if __name__ == '__main__':
    main()
