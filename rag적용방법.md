# 온톨로지 YAML 작성에 RAG(LightRAG) 적용 방법

> 결론 요약: LightRAG를 **YAML 생성기**로 쓰는 것은 부적합하다. **문서 분석 보조(후보 추출)** 단계로
> 쓰는 것은 가능하며, 최종 YAML은 사람이 확정하고 `schema validate`로 검증해야 한다.

---

## 1. LightRAG는 무엇을 하는 도구인가

LightRAG는 **문서를 그래프로 만들어 검색하는 RAG 프레임워크**다.

```
PDF / SOP / 영업 메모
   → (LLM으로) 엔티티·관계 추출
   → 트리플 그래프 저장
   → 듀얼레벨(low/high) 검색으로 질의응답
```

출력은 대략 다음과 같은 자유 형식 JSON이다:

```json
{
  "entities": [
    {"id": "참이슬", "type": "product"},
    {"id": "A마트", "type": "outlet"}
  ],
  "relations": [
    {"src": "A마트", "tgt": "참이슬", "rel": "주문한다"}
  ]
}
```

핵심은 **검색 품질**이지, 스키마 정의가 아니다.

## 2. 이 레포의 YAML이 요구하는 것

`ontology/domains/<name>/` 아래 YAML은 단순 데이터가 아니라 **검증되는 스키마 + 쓰기 경로 +
코드 생성의 원천(source of truth)**이다.

```yaml
# ontology/domains/liquor/object_types/Product.yaml
apiName: Product                       # 카멜케이스 고정 식별자
primaryKey: sku
properties:
  category:
    apiName: category
    type: enum
    values: [소주, 맥주, 탁주, 청주, 양주, 와인, 기타]   # 도메인 enum 직접 관리
    required: true
    indexed: true
  unitPrice:
    type: integer
    min: 0
    required: true
```

```yaml
# ontology/domains/liquor/link_types/orderLineProduct.yaml
- apiName: orderLineProduct
  fromObjectType: SalesOrderLine
  fromApiName: product
  fromCardinality: one
  toObjectType: Product
  toApiName: orderLines
  toCardinality: many
```

```yaml
# ontology/domains/liquor/action_types/CreateSalesOrder.yaml
parameters:
  lines:
    type: json
rules:
  - type: runFunction
    function: createSalesOrder    # → src/ontology_runtime/domains/liquor/ 에 실제 Python 함수 필요
```

즉 YAML 하나가 다음을 모두 결정한다.

- 프로퍼티 타입·필수·유일·인덱스·범위
- 링크 카디널리티(`one` / `many`)와 양방향 apiName
- 액션 파라미터, 허용 역할(`allowedRoles`), 에이전트 제안 가능 여부(`agentProposable`)
- `runFunction` 으로 연결되는 **실제 Python 구현체**

## 3. LightRAG 출력을 그대로 쓸 수 없는 이유

| 항목 | LightRAG 출력 | 이 YAML이 요구하는 것 |
|---|---|---|
| 이름 | LLM이 멋대로 생성 ("A마트", "주문한다") | 카멜케이스 `apiName`, `primaryKey`, 링크의 `fromApiName`/`toApiName` |
| 타입 | 대충 `type: product` | `enum` + `values`, `required`/`unique`/`indexed`, `min`/`max`, `defaultValue` |
| 관계 | 하나의 트리플 | 방향·카디널리티가 명시된 링크 타입 파일 1개 |
| 동작 | 없음 | `runFunction` → 실제 Python 코드, `allowedRoles`, `agentProposable` |
| 검증 | 없음 | `ontology schema validate`, `/validate` 드라이런 |
| 결정성 | 비결정적(매 실행 결과가 다름) | 리뷰 가능한 소스 오브 트루스 |
| 생성물 연동 | 없음 | `export-web`, `docs`, `seed` 와의 정합성 |

구체적인 예: LightRAG는 "Outlet이 Product를 주문한다"는 단일 관계를 뽑지만, 이 레포에서는
반드시 `Outlet → SalesOrder → SalesOrderLine → Product` **4단계 경로**로 모델링해야 한다.
게다가 `taxType` 값 범위, `unitsPerCase` 같은 도메인 제약, 링크 카디널리티는 LLM 추출로는
나오지 않는다.

## 4. 쓸 만한 자리: "YAML 작성 전 문서 분석" 단계

LightRAG는 **작성 보조 도구**로는 의미가 있다. 위치는 YAML을 쓰기 *전*이다.

```
[1단계] 영업 SOP, 납품 규정, 상품 카탈로그, 거래처 명세 등을 LightRAG에 적재
        → 엔티티 후보(Outlet / Product / SalesOrder / Delivery …)와 관계 후보 JSON 추출
[2단계] 사람(또는 에이전트)이 검토하여 확정
        - 카멜케이스 apiName, primaryKey 선정
        - 프로퍼티 타입·required·indexed·범위 결정
        - 링크 방향과 카디널리티 결정
[3단계] ontology/domains/<name>/object_types|link_types|action_types/ 에 YAML 작성
[4단계] uv run ontology --domain <name> schema validate   ← 실제 합격 기준
```

이 경우 LightRAG의 비결정성은 문제가 되지 않는다. 출력은 **후보(candidate)** 일 뿐이고,
최종 판단과 검증은 4단계가 담당하기 때문이다.

반대로 하면 안 되는 패턴:

- LightRAG 출력을 받아 곧바로 `object_types/*.yaml`로 덮어쓰기
- 추출된 엔티티명을 그대로 `apiName`으로 사용 (카멜케이스·primaryKey 규칙 위반)
- 액션이나 함수 바인딩까지 자동 생성 시도 (`runFunction` 이 가리킬 Python 구현체가 없음)

## 5. 더 어울리는 대안: 기존 propose → approve 패턴 확장

이 레포에는 이미 **에이전트가 제안하고 사람이 승인하는** 워크플로우가 있다
(`ontology/platform/` 의 `ActionProposal`, `AgentRun`, `applyApprovedProposal`).
온톨로지 정의 변경도 같은 패턴으로 끌고 가는 것이 낫다.

```
에이전트(읽기 전용 도구: search_objects, get_linked_objects, run_function)
   → object_types/link_types YAML "diff 제안" 생성        (validate_action 과 유사)
   → schema validate + /validate 드라이런으로 자동 검증
   → 사람 승인(applyApprovedProposal 과 유사)
   → 반영 후 uv run ontology export-web , uv run ontology --domain <name> docs
```

장점:

- **결정적이고 리뷰 가능**하다 — diff로 무엇이 바뀌었는지 그대로 보인다.
- **하나의 쓰기 경로** 원칙이 유지된다. (CLAUDE.md: "Do not add a second persistence path")
- 에이전트는 여전히 **직접 쓸 수 없다** — 제안만 하고 승인은 사람이 한다.
- 기존 `Violation` / `OntologyError` 엔벨로프를 그대로 재사용할 수 있다.

## 6. 요약

| 사용 방식 | 적합성 | 이유 |
|---|---|---|
| LightRAG를 YAML **생성기**로 사용 | ❌ 비추 | 스키마 검증, 함수 바인딩, 네이밍 규칙, 결정성 모두 미흡 |
| LightRAG를 **문서 분석 보조**로 사용 | ⚠️ 가능 | 후보 추출까지만. 최종 YAML은 사람이 확정 후 `schema validate` |
| 기존 **propose → approve** 패턴 확장 | ✅ 권장 | 결정적·리뷰 가능·단일 쓰기 경로 유지 |

실무 권장 조합:

1. 신규 도메인 기획 초기에 문서를 LightRAG에 넣어 **후보 엔티티/관계**를 뽑는다.
2. 후보를 바탕으로 `ontology/domains/<name>/` YAML을 **직접 작성**한다.
3. `schema validate` → `seed` → `export-web` → `docs` 순서로 검증·생성한다.
4. 이후 정의 변경은 propose → approve 워크플로우로 관리한다.

## 관련 명령어

```bash
uv run ontology domains                                    # 도메인 목록
uv run ontology --domain <name> schema validate            # 스키마 검증
uv run ontology --domain <name> seed --seed 42             # 시드 데이터
uv run ontology export-web                                 # 웹 클라이언트 생성
uv run ontology --domain <name> docs                       # 문서 생성
```
