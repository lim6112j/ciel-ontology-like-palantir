# 외부 양조장 DB 연동 계획 (보류 중)

> **상태: 보류.** 실제 양조장 DB 접근이 가능해지면 이 문서의 체크리스트대로 진행한다.
> 2026 년 협의 내용을 정리한 것. 코드 변경은 아직 없음.

## 1. 배경: 현재 양조장 데이터의 상태

- 양조장 데이터는 `makgeolli` 도메인(`ontology/domains/makgeolli/`) 전체가 담당한다.
  - 양조 코어: `Batch`, `Tank`, `TempReading`, `RawMaterial`, `Product`
  - 판매·유통: `SalesOrder`/`SalesOrderLine`, `Shipment`, `WasteRecord`,
    `WarehouseStock`, `OutletStock`, `Customer`
- 현재 데이터는 **100% 합성(synthetic)** 이다.
  - 생성기: `src/ontology_runtime/domains/makgeolli/seed/generator.py`
  - 마스터 데이터(제품 10종·고객 5·탱크 4·원재료 6)는 코드 하드코딩
  - 거래 데이터는 `random.Random(42)` 기반 결정론적 생성 → `--seed 42`로 재현 가능
  - 실행: `uv run ontology --domain makgeolli seed --seed 42`
- 저장 위치: 로컬 Docker PostgreSQL 16 (포트 `55432`), **도메인별 DB 분리**
  (`ontology`, `ontology_bakery`, `ontology_makgeolli` 등 확인됨)
- 저장 구조: 범용 6개 테이블 — `objects`(JSONB), `links`, `action_runs`,
  `action_edits`, `agent_runs`, `ontology_indexes`. "Product 테이블" 같은
  도메인 전용 테이블은 없음. 타입/검증은 YAML 스키마 + 런타임이 담당.
- 요약: **저장은 실제(JSONB 행), 내용은 가상(시드 생성).** 실제 양조장 DB와의
  결합 지점은 현재 존재하지 않는다.

## 2. 결론 (협의 요지)

- **온톨로지 기반이라 외부 DB 연동이 어려운 게 아니라 오히려 유리하다.**
  온톨로지는 저장 형식이 아니라 의미 계층이고, 내부 스토어는 범용 JSONB라서
  외부 스키마와 충돌하지 않는다.
- **진짜 제약은 "단일 쓰기 경로"** — 모든 쓰기는 `ActionService` → `EditBatch`
  → 검증 → 감사로 흐른다. 외부 DB를 직접 읽고/쓰는 실시간 페더레이션은 이
  원칙을 깨므로 하지 않는다(최대한 읽기 전용 뷰 수준만).

### 통합 패턴 비교

| 패턴 | 설명 | 판정 |
|---|---|---|
| A. 인제스트 커넥터 (권장) | 양조장 DB **읽기 전용** 풀링 → 매핑 → `ObjectStore` 벌크 업서트. 시드의 `ObjectStore` 벌크 쓰기 패턴을 일반화한 것 | ✅ 채택 |
| B. 액션 기반 흡수 | 양조장 이벤트(생산/출고/재고)를 액션 파라미터로 변환 → `propose_action` → 승인 → 적용. 감사 완전, 기존 워크플로우와 결합 | ✅ 보조로 사용 |
| C. 실시간 페더레이션 | store 레이어를 외부 DB 위에 얹기 | ❌ 기각 |

- 패턴 A+B 병행: 마스터/재고 스냅샷은 A(벌크 업서트), 운영 이벤트는 B(제안→승인).
- 망 분리로 직접 접속이 불가하면 A의 앞단만 CSV/API 배치 업로드로 교체.

## 3. 스키마 분석 프로세스 (접근 가능해지면 실행)

분석의 최종 산출물은 **매핑 설계**다. 외부 DB를 그대로 쓰는 게 아니라
외부 테이블 → 온톨로지 객체 타입으로 번역해야 한다.

```
① 읽기 전용 접속 확보 (계정 권한 최소화)
② information_schema 프로파일링: 테이블/컬럼/PK/FK/행수/샘플값
③ 엔터티 분류: object 후보 / link 후보 / 제외
   - 실체 테이블(생산배치·제품·창고) → object type 후보
   - N:M 관계 테이블 → link type 후보
   - 순수 로그성 테이블 → 배제 또는 이벤트 스트림(B 패턴)
④ 매핑 초안 YAML 작성: 컬럼 → property, FK → linkType
⑤ 샘플 데이터로 검증 시뮬레이션: 우리 검증 파이프라인에 통과시켜보기
⑥ 사람 검토 → 매핑 확정 → 커넥터 구현
```

- ②~④는 자동화 가능: "외부 DB 스키마를 읽어 object_type YAML 초안을 생성하는
  프로파일러 스크립트"가 합리적인 첫 구현물. 초안은
  `ontology/domains/makgeolli/external/` 같은 곳에 두고 사람이 다듬는다.

### 타입 매핑 규칙

외부 컬럼 타입 → 우리 `PropertyType` 11종으로 수렴:
`string, text, integer, bigint, decimal, boolean, date, timestamp, enum, objectRef, json`

- `VARCHAR(n)`, `CHAR(n)` 코드값 → `string` 또는 코드 목록 확인 후 `enum`
- `NUMERIC(p,s)` → `decimal`
- `TIMESTAMPTZ` → `timestamp` (저장은 ISO 텍스트 — 프로젝트 규칙 참고)
- 애매한 것은 `string` + 검증 규칙으로 내린다.

## 4. 실행 시 반드시 지킬 것 (주의점 4가지)

1. **식별자 매핑**: 외부 PK ↔ 우리 RID 매핑 테이블을 만든다. 동기화 멱등성의
   핵심 — 같은 원본 레코드는 항상 같은 객체로 업데이트.
2. **진실의 원천(source of truth) 구분**: 객체 타입별로 명시한다.
   - 생산기록·재고·배치: 양조장 DB가 원천 → 우리 쪽 임의 수정 금지,
     수정 필요하면 역방향 제안 생성
   - 주문·제안·승인: 우리가 원천
3. **검증 충돌 정책**: 외부 데이터가 프로퍼티 검증/불변식을 통과 못 할 수 있다.
   임포트 경로는 검증 파이프라인(`EditContext` 포함)을 그대로 타되,
   실패 건은 스킵 + 리포트. "검증 완화 vs 데이터 정제"는 ⑤ 결과로 결정.
4. **스키마 드리프트**: 외부 스키마 변경은 매핑 YAML만 고쳐 흡수한다(온톨로지 장점).

## 5. 접근 가능해졌을 때 체크리스트

- [ ] 양조장 DB 읽기 전용 접속 확보 (접속 정보는 `.env`에, 커밋 금지)
- [ ] ② 프로파일링 스크립트 실행 → 테이블 인벤토리 작성
- [ ] ③ 엔터티 분류 회의 (object / link / 제외 + 원천 방향 결정)
- [ ] ④ 매핑 초안 YAML 생성 (프로파일러) → 사람 검토
- [ ] ⑤ 샘플 데이터 검증 시뮬레이션 → 실패 유형 리포트
- [ ] RID 매핑 테이블 설계 (외부 PK ↔ RID, 동기화 멱등성)
- [ ] 커넥터 구현: `ObjectStore` 벌크 업서트 + `sync` CLI 커맨드
      (예: `uv run ontology --domain makgeolli sync`)
- [ ] 운영 이벤트 → `propose_action` 파이프라인 연결 (B 패턴)
- [ ] 테스트: 시드 데이터 ↔ 커넥터 데이터 격리 확인 (TRUNCATE 충돌 주의)

## 6. 열린 질문

- 실제 대상 양조장 DB의 종류/버전/접근 경로 (PostgreSQL? MSSQL? ERP 내장?)
- 도메인 배치: `makgeolli` 도메인에 양조장 외부 객체를 추가할지,
  별도 도메인(예: `brewery`)으로 분리할지
- 동기화 주기와 트리거 (배치? 이벤트?)
