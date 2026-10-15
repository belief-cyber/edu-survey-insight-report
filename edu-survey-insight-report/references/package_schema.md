# 분석 패키지 데이터 구조 (education-analysis-package-v1)

패키지는 ZIP 하나에 아래 파일이 들어 있다. `inspect_package.py`가 필수 파일·SHA256·건수를 확인한다.
다른 버전의 패키지가 오면 이 문서의 열 이름과 실제 파일을 먼저 대조하고, 다르면 `scripts/common.py`의 열 이름만 고친다.

## 키와 관계

```
educations.csv ──교육ID──┬─ participation.csv (1:1)
                         ├─ survey_responses.csv (1:N, 비식별응답ID)
                         │        └─ question_answers.csv (1:N, 비식별응답ID)
                         ├─ qualitative.csv (1:N, 비식별응답ID·비식별주관식ID)
                         ├─ quantitative_summary.csv (교육·원문항 / 전체교육 집계)
                         └─ question_dictionary.csv (원본문항ID ↔ 표준분석항목ID)
```
익명 설문은 참여자 명단과 개인 단위로 연결하지 않는다(교육ID 단위만 연결).

## 파일별 주요 열

| 파일 | 주요 열 | 쓰임 |
|---|---|---|
| `manifest.json` | package_version, export_id, dataset_version_id, analysis_run_id, qualitative_run_id, counts, files.sha256, validation, privacy | 데이터 버전 표기, 무결성 확인 |
| `analysis_rules.md` | 패키지 측 계산 규칙 | 매번 읽고 `references/analysis_rules.md`와 다른 점이 있으면 패키지 규칙을 우선 |
| `educations.csv` | 교육ID, 교육명, 연도, 학기, 교육유형, 운영방식, 교육시작일, 교육종료일, 교육대상, 신청자수_기준표, 참여자수_기준표, 설문응답수_기준표, 참여자자료상태, 설문자료상태 | 교육 메타. **교육ID 앞 4자리 = 학년도**(연도 열과 다를 수 있음) |
| `participation.csv` | 교육ID, 참여자레코드수, 확인된이수자수, 설문응답수, 응답률계산가능(Y/N), 응답률분모, 응답률 | 응답률은 `응답률계산가능=Y`일 때만 사용 |
| `survey_responses.csv` | 비식별응답ID, 교육ID, 응답자신분(학부생/대학원생/교수/교직원/미분류), 유효응답수, 주관식응답수, 중복의심 | 응답자 단위 |
| `question_answers.csv` | 문항응답ID, 비식별응답ID, 교육ID, 원본문항ID, 원문항, 표준분석항목ID, 지표변형, 원본응답값, 수치값, 비교가능성(A/B/C/D), 분석포함(Y/N), 제외사유, 변환상태 | 정량 원자료 |
| `qualitative.csv` | 비식별주관식ID, 비식별응답ID, 교육ID, 원문항, 비식별원문, 주제, 의견유형, 코딩상태(PROPOSED/APPROVED/REJECTED), 분석제외(Y/N), 제외사유 | 주관식. `분석제외=N`만 분석 |
| `question_dictionary.csv` | 표준분석항목ID, 표준한글명, 원래질문문구, 원본문항ID, 교육ID, 원래응답척도, 비교집계가능성 | 문항 의미·척도 확인 |
| `quantitative_summary.csv` | 집계수준(전체교육/교육·원문항), 교육ID, 표준분석항목ID, 원문항, 유효응답수, 평균, 표준편차, 교육수, 교육동일가중평균, 응답분포 | **검증 기준표** — 재계산 결과가 반드시 일치해야 함 |
| `education_groups.csv` | 교육군ID, 교육군명, 교육ID, 상태 | 승인된 교육군(있으면 대상 탐색에 참고) |
| `improvement_history.csv` | 개선ID, 제목, 영역, 계획내용, 상태, 관련교육ID, 실행일 … | 비어 있으면 "개선 효과 추적 불가"로 명시 |

## 표준 지표 (표준분석항목ID)

| ID | 한글명 | 비고 |
|---|---|---|
| overall_satisfaction | 전반적 만족도 | 명시적 원문항만(산출열·중복열은 분석포함=N) |
| content_usefulness | 교육내용 유익성 | 교육에 따라 문항 없음 |
| delivery_method_satisfaction | 진행방식 만족도 | 비교가능성 B(조건부) |
| instructor_delivery | 강사 전달력 | |
| class_duration_satisfaction | 교육시간 만족도 | |
| goal_attainment | 핵심역량 향상 도움도 | 교육마다 목표 문구가 다름. 한 교육에 문항 2개 이상이면 통합 평균 제외 |
| difficulty_appropriateness | 난이도 적절성 | 척도 방향 미검증 → 분포만 |
| participation_goal_achievement_help | 참여 목적 달성 도움도 | goal_attainment와 별도 지표(합산 금지) |
| respondent_status / affiliation_major / awareness_channel | 신분·소속·인지경로 | 추정 인원 시그니처에 사용 |
| open_feedback / future_training_demand / complex_program_operations_feedback | 주관식 | 정성분석 |

## 비교가능성 등급
A 직접 비교 · B 조건부 비교 · C 원문 보존(집계 불가) · D 교육 고유 문항(비교 불가). 정량 평균은 A·B만.
