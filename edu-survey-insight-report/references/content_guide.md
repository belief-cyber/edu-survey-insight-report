# report_content.json 작성 가이드

`content_skeleton.py`가 초안을 만들고, 분석자가 TODO를 채운다. 사실 문장은 `quant_summary.md`·`qual_summary.md`의 값만 쓰고, 해석은 해석 칸에만 쓴다.

## 공통 형식
- 문자열 안 `**굵게**`만 지원(나머지는 그대로 출력).
- 근거 객체 `ev`: `{"q": [주관식ID…], "r": [응답ID…], "edu": [교육ID…], "theme": "코드", "scope": "TARGET|OTHER"}` — 필요한 키만. 화면에 근거 버튼으로 나타난다.
- 수치에는 분석 대상과 n을 붙인다(예: "4.72(n=53)", "3점 이하 5/53").
- 사실과 해석 분리: 정량·정성 근거 칸 = 확인된 사실, `interp`·`implication`·`thinks`·`feels`·권고의 방향/아이디어 = AI 해석.
- 필터에 따라 해석이 바뀌는 것처럼 쓰지 않는다(“선택한 범위에서는 …” 금지). 각 해석에 고정 `scope`를 쓴다.

## 키별 설명
| 키 | 내용 |
|---|---|
| doc_title, header_sub, title, subtitle, purpose | 머리말. purpose = 사용자가 준 분석 목적 |
| summary.question / scope / rows[{k, items[{text, ev}]}] | 핵심 답변. k는 보통 유지·강화 / 우선 개선 / 검토·탐색 |
| data_lead, data_notes[{badge: warn/fact/fix, title, text, ev}] | 데이터 특성. 스켈레톤이 자동 작성 → 다듬기 |
| explorer_interpretation{scope, items[]} | 전체 교육 탐색 결과 해석(교란 요인, 천장효과 등) |
| difficulty_warning | 난이도 선택 시 경고 문구 |
| target_lead | 대상 교육 개요 + 교육 간 차이 검정 결과 |
| target_default_metric | 대상 분포 차트 기본 지표 인덱스(0 전반, 1 유익성, 2 진행방식, 3 강사, 4 교육시간, 5 핵심역량) |
| sensitivity{exclude[응답ID], label, reason} | 척도 역방향 의심 응답 민감도 토글. 없으면 빈 배열 |
| target_cards{교육ID: [특징]} | 교육별 특징 카드(이 교육에서만 나타난 것) |
| anomalies[{title, text, ev}] | 응답 패턴 이상 |
| compare_note | 비교군 구성 설명 |
| insights[{title, tag, scope, obs, quant, qual, interp, implication, ev}] | 관찰→정량→정성→해석→시사점. tag: 대상 특화 / 전체 공통 / 공통 vs 특화 / 근거 일치 / 해석 제한 |
| dt_scope | 디자인 씽킹 분석 범위 |
| issue{user, need, goal, problem, action: {text, kind: fact/ai/mixed, ev}} | 이슈 구조화 |
| persona_note, personas[{name, desc, tags, ev}] | 유형. 근거 부족하면 personas=[]와 한계 설명 |
| empathy{center, says[], thinks[], does[], feels[{tone pos/neg/neu}], pains, gains, needs} | says는 원문 인용 + ev.q 필수 |
| pain_points[{title, type, context, strength 1~3, strength_label, ev}], pain_relation | strength는 근거 강도 표시(점수 아님) |
| problem_statements[{scope, situation, need, because}] | “사용자는 [상황에서] [필요]. 왜냐하면 [확인된 이유]” |
| hmw[{q, basis, ev}] | q는 "우리가 어떻게 하면"을 빼고 작성(템플릿이 붙임). 해법을 전제하지 않는 열린 질문 |
| recommendations[{id, tier, title, who, need, evidence, direction, ideas, effect, constraints, evaluation, ev}] | tier: t1 우선 검토 / t2 검토 / t3 탐색 / t0 유지. effect는 "(예상)"으로 시작 |
| limitations[] | 표본, 추정 인원, 코딩 신뢰도, 척도 확인 필요 등 |

## 작성 원칙
1. **전체 교육 vs 대상 교육을 섞지 않는다.** 전체 교육의 반복 요구는 "전체 공통", 대상에서만 나온 것은 "대상 특화"로 태그.
2. **신분으로 페르소나를 만들지 않는다.** 신분별 정량 차이와 주관식 근거가 함께 있을 때만 유형으로 쓰고, 아니면 "상황·요구 기준 잠정 유형"으로 쓰거나 비운다.
3. **인과를 단정하지 않는다.** "~때문이다"는 문제 재정의의 because에서도 *분석으로 확인된 이유*만.
4. **HMW는 열린 질문.** 나쁜 예: "복사-수정 실습지를 도입해 타자 부담을 없앨 수 있을까?"(해법 전제). 좋은 예: "60분 안에서 다음 일정에 쫓기지 않으면서 충분히 배웠다고 느끼게 할 수 있을까?"
5. **권고에는 점수·순위 숫자를 만들지 않는다.** 중요도와 근거 충분성으로 tier만 고른다. 근거가 1~2명이면 t3(탐색) 또는 "시범 운영"으로.
6. 각 권고에 차기 설문에서 효과를 확인할 **평가 방법**(기존 문항 또는 신규 문항 「…」)을 쓴다.
7. 데이터에 없는 운영 정보(예산, 강의실 제약)는 "데이터 외 운영 정보"라고 표시하거나 사용자에게 확인.
8. 담당자가 확인해 준 사실(예: 분할 영상 전환)은 출처를 "담당자 확인"으로 적는다.

## 검증
`validate_content.py`가 오류(필수 항목, TODO, 없는 ID/코드, 원문에 없는 “인용”, tier, 점수 필드)를 막고, 정량 결과에서 찾지 못한 소수 값을 경고한다. 경고는 직접 확인하고, 계산한 값이면 quant_summary/추가 계산 근거를 남긴다.
