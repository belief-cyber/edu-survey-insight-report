---
name: edu-survey-insight-report
description: "ERICA 학술정보관 학술정보교육 AI 분석 패키지(education_analysis_*.zip, manifest.json·question_answers.csv·qualitative.csv 포함)를 받아 특정 교육/교육군(예 월간 AI 한입 세션, 릴레이 특강, 첫걸음 가이드)의 정량·정성 통합분석을 하고, 공감맵·페르소나·Pain Point·HMW·개선 권고와 필터·차트·근거 조회가 있는 독립형 인터랙티브 HTML 보고서를 만든다. 교육 설문 결과 분석, 만족도·주관식 종합, 차기 교육 기획 근거, 교육 개선 보고서를 요청받으면 패키지 이름을 말하지 않아도 이 스킬을 사용한다."
---

# 학술정보교육 정량·정성 통합분석 보고서

입력: **분석 패키지 ZIP + 대상 교육명(또는 교육군·교육ID) + 분석 목적**.
산출: 검증된 독립형 HTML 보고서 1개 + 채팅 요약(핵심 답변, 데이터 버전, 검증 결과).

이 스킬의 목적은 "전체 교육의 공통 요구와 대상 교육의 특화 요구를 근거로, 다음 교육에서 무엇을 유지·개선할지"에 답하는 것이다. 수치는 모두 스크립트로 계산하고 공식 집계표와 맞춰 보며, 해석은 사실과 분리해 쓴다. 이전 분석의 수치나 결론을 재사용하지 않는다 — 매번 새 패키지에서 다시 계산한다.

## 준비
```bash
SKILL=<이 SKILL.md가 있는 폴더>; W=<작업 폴더, 예: ./work_<대상>>
pip install pandas numpy scipy playwright --break-system-packages  # 없을 때만. scipy는 선택
```
패키지 ZIP은 사용자 업로드 원본이므로 작업 폴더로 풀어서 쓴다(원본 수정 금지).

## 절차 (작업 목록으로 만들어 진행 상황을 보여준다)

**1. 패키지 점검** — `python3 $SKILL/scripts/inspect_package.py <zip> --work $W`
SHA·필수 파일·데이터 특성(설문 누락, 연도 불일치, 메타 공란, 응답률 가능 범위, 분할 운영 단위, 개선 이력, 코딩 상태)과 교육군 목록을 출력한다. 패키지 안의 `analysis_rules.md`도 읽어 `references/analysis_rules.md`와 다른 규칙이 있으면 패키지 규칙을 따르고 사용자에게 알린다.

**2. 대상 확정** — `python3 $SKILL/scripts/find_target.py --work $W --query "<교육명>" [--year 2026] [--label "표시명"] --similar "AI,GPT,…" --purpose "<분석 목적>"`
- 여러 교육군이 걸리거나 연도가 섞이면 목록을 보여주고 범위를 확인한다(`--ids`로 직접 지정 가능).
- `--similar`는 유사 주제 비교군 키워드다. 대상 주제에서 2~5개를 고르고 무엇을 골랐는지 밝힌다.

**3. 정량분석** — `python3 $SKILL/scripts/quant.py --work $W` → `quant_results.json`, `quant_summary.md`
- 맨 위 "공식 집계 재현"이 7개 모두 일치해야 진행한다. 불일치면 멈추고 원인을 보고한다.
- `quant_summary.md`를 전부 읽는다: 연도·유형·운영방식·신분·비교군(설문 행/추정 인원), 대상 교육별·문항별 결과, 대상 통합과 Kruskal-Wallis p, 신분별, 인지경로, 이상 패턴(양극단·단독 1점·저점 응답), 분할 단위.
- 규칙과 해석 제한은 `references/analysis_rules.md`. 특히: 응답자 가중 vs 교육 동일가중 구분, 복수 문항 지표는 문항별로만, 난이도 양극단이면 분포만, 핵심역량 ≠ 실제 역량, 분할 영상교육은 추정 인원 기준 병기, 유의성 미확인 차이는 단정 금지.
- 추가 계산이 필요하면 `scripts/common.py`의 `load/valid/integrated/agg_values`로 계산하고 그 값을 근거로 남긴다.

**4. 정성분석(전수)** — `python3 $SKILL/scripts/qual_prep.py --work $W`
→ `qual_review.md`를 **모두 읽고** `overrides.json`에 판단을 기록 → `python3 $SKILL/scripts/qual_finalize.py --work $W`
- 절차·판정 기준·인용 규칙: `references/qualitative_coding.md`. 코드북: `assets/codebook.json`.
- 같은 데이터 버전으로 이미 만든 overrides.json이 있으면 재사용하고 대상 교육 행만 다시 확인한다.
- 마스킹 기록을 확인한다(실명 오탐·누락).

**5. 해석 작성** — `python3 $SKILL/scripts/content_skeleton.py --work $W` → `$W/report_content.json`의 TODO를 채운다.
- 키별 설명·작성 원칙: `references/content_guide.md`. 핵심: 관찰→정량 근거→정성 근거→담당자 관점 해석→기획 시사점, 전체 공통 vs 대상 특화 구분, 신분만으로 페르소나 만들지 않기, 열린 HMW, 점수 없는 단계형 우선순위, 권고마다 차기 설문 평가 방법.
- 모든 주요 문장에 `ev`(주관식ID·응답ID·교육ID·주제코드)를 연결한다.
- `python3 $SKILL/scripts/validate_content.py --work $W --content $W/report_content.json` — 오류 0이 될 때까지 고치고, 경고(정량 결과에서 못 찾은 수치)는 하나씩 확인한다.
- 사용자가 "먼저 분석 결과를 채팅으로 검토"를 원하면 여기서 멈추고 핵심 답변·인사이트·권고를 채팅으로 보여준 뒤 피드백을 반영한다.

**6. HTML 생성** — `python3 $SKILL/scripts/build_report.py --work $W --content $W/report_content.json --out $W/<파일명>.html`
템플릿 구조·디자인 규칙: `references/report_design.md`. 수치를 HTML에 직접 쓰지 않는다(브라우저가 원자료로 재계산).

**7. 브라우저 검증** — `python3 $SKILL/scripts/verify_report.py --work $W --html $W/<파일명>.html`
공식 집계 일치, 필터·집계 기준·지표 전환, 교육별 표 행 수, 드로어, 주관식 범위 수, 히트맵·셀 클릭, 민감도 토글, 근거 ID 해석, 모바일 가로 스크롤, 콘솔 오류, 인쇄 PDF 쪽수를 확인한다. FAIL이 있으면 고치고 다시 실행한다. `shots/`의 스크린샷(s0, s3, s4 등)을 직접 열어 겹침·잘림을 눈으로 확인한다.

**8. 전달** — HTML 파일을 사용자에게 보내고 채팅에는 다음만 짧게 쓴다.
- 대상 교육(ID·교육 수·응답 수), 사용한 데이터 버전(dataset_version_id, 실행 ID)
- 핵심 답변(유지 / 개선 3~5줄)
- 검증 결과(공식 집계 일치 여부, 브라우저 검사 통과 수, 인쇄 쪽수)
- 해석 제한·확인이 필요한 사항(척도, 추정 인원, 표본)

## 판단이 필요한 지점
- 패키지 버전·열 이름이 `references/package_schema.md`와 다르면 열 대응을 확인한 뒤 `common.py`를 고친다.
- 분할 운영의 범위(어떤 운영방식을 분할로 볼지), 이상 응답의 민감도 제외 여부, 데이터에 없는 운영 제약(예산·공간)은 사용자에게 확인한다. 사용자가 없으면 가장 보수적인 선택을 하고 보고서 한계에 적는다.
- 대상 교육의 주관식이 매우 적으면(예: 10명 미만) 유형·공감맵을 무리하게 채우지 말고 한계를 쓴다.

## 파일
- `scripts/common.py` 공통 규칙 · `inspect_package.py` · `find_target.py` · `quant.py` · `qual_prep.py` · `qual_finalize.py` · `content_skeleton.py` · `validate_content.py` · `build_report.py` · `verify_report.py`
- `assets/report_template.html` 보고서 템플릿 · `assets/codebook.json` 주관식 코드북
- `references/package_schema.md` 데이터 구조 · `analysis_rules.md` 계산 규칙 · `qualitative_coding.md` 코딩 절차 · `content_guide.md` 해석 작성 · `report_design.md` 보고서 구조
- `examples/report_content_example.json` 가상 작성 예시(형식 참고용 — 교육명·수치·인용은 모두 가상)
