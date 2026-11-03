import { useEffect, useRef, useState } from 'react';

import type { DiagramCounts } from '../generated/domains';

interface Props {
  open: boolean;
  domainName: string;
  displayName: string;
  source: string;
  counts: DiagramCounts;
  onClose: () => void;
}

/** Action edges are drawn with the non-identifying marker, so they can be dropped. */
const ACTION_EDGE = '..o{';

function withActions(source: string, showActions: boolean): string {
  if (showActions) return source;
  return source
    .split('\n')
    .filter((line) => !line.includes(ACTION_EDGE))
    .join('\n');
}

/**
 * Renders the domain's generated Mermaid erDiagram.
 *
 * The diagram text comes from `generated/<domain>/diagram.ts`, so it is always
 * in sync with the YAML. Mermaid itself is imported lazily: it is only needed
 * when an operator opens this dialog.
 */
export function OntologyDiagram({
  open,
  domainName,
  displayName,
  source,
  counts,
  onClose,
}: Props) {
  const canvas = useRef<HTMLDivElement>(null);
  const [showActions, setShowActions] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setError(null);
    void (async () => {
      try {
        const { default: mermaid } = await import('mermaid');
        if (cancelled) return;
        mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'dark' });
        const { svg } = await mermaid.render(
          `ontology-diagram-${domainName}`,
          withActions(source, showActions),
        );
        if (cancelled || !canvas.current) return;
        canvas.current.innerHTML = svg;
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, domainName, source, showActions]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="diagram-overlay" onClick={onClose} role="presentation">
      <div
        className="diagram-modal"
        role="dialog"
        aria-modal="true"
        aria-label={`${displayName} 온톨로지 다이어그램`}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="diagram-head">
          <div>
            <h2>{displayName} 온톨로지 다이어그램</h2>
            <p className="muted">
              오브젝트 {counts.objectTypes}개 · 링크 {counts.linkTypes}개 · 액션 {counts.actionTypes}개
              (에이전트 제안 가능 {counts.agentProposableActions}개)
            </p>
          </div>
          <div className="actions">
            <label className="diagram-toggle">
              <input
                type="checkbox"
                checked={showActions}
                onChange={(event) => setShowActions(event.target.checked)}
              />
              액션 표시
            </label>
            <button className="ghost" onClick={onClose}>
              닫기
            </button>
          </div>
        </header>
        {error ? (
          <div className="banner error">다이어그램을 그리지 못했습니다: {error}</div>
        ) : (
          <div className="diagram-canvas" ref={canvas} />
        )}
        <footer className="diagram-legend muted">
          <span className="legend-item">
            <i className="swatch object" /> 오브젝트 타입
          </span>
          <span className="legend-item">
            <i className="swatch action" /> 액션 타입
          </span>
          <span>
            PK 기본키 · UK 유니크 · FK 객체 참조. 액션은 점선으로 읽기·생성·수정하는 객체에 연결됩니다.
          </span>
        </footer>
      </div>
    </div>
  );
}
