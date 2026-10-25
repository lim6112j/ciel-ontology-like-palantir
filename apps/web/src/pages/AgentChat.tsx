import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';

import { AGENTS, api } from '../generated';

interface Turn {
  role: 'user' | 'assistant';
  text: string;
  toolCalls?: { tool: string; isError?: boolean; result?: string }[];
  proposals?: string[];
  runNo?: string;
}

const PRESETS = [
  '행복식당 소주 5박스 내일 배송으로 접수해줘',
  '2026-10-27 배차 계획 세워줘',
  '오늘 배송에서 문제가 있는 정류장 알려줘',
  '이번 주 기사별 실적을 요약해줘',
];

export function AgentChat() {
  const [agent, setAgent] = useState<string>(AGENTS[0]?.apiName ?? 'orderIntakeAgent');
  const [input, setInput] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);

  const invoke = useMutation({
    mutationFn: (message: string) => api.invokeAgent(agent, message),
    onSuccess: (result) => {
      const payload = result.data;
      setTurns((current) => [
        ...current,
        {
          role: 'assistant',
          text:
            payload.finalMessage ||
            (payload.proposals.length
              ? `제안 ${payload.proposals.length}건을 인박스에 올렸습니다.`
              : '(응답 없음)'),
          toolCalls: payload.toolCalls,
          proposals: payload.proposals,
          runNo: payload.runNo,
        },
      ]);
    },
    onError: (error: Error) => {
      setTurns((current) => [
        ...current,
        { role: 'assistant', text: `호출에 실패했습니다: ${error.message}` },
      ]);
    },
  });

  const send = (text: string) => {
    const message = text.trim();
    if (!message || invoke.isPending) return;
    setTurns((current) => [...current, { role: 'user', text: message }]);
    setInput('');
    invoke.mutate(message);
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>운영 어시스턴트</h1>
          <p>
            에이전트는 온톨로지를 읽고 <strong>제안만</strong> 만듭니다. 실행은 제안 인박스에서
            승인해야 일어납니다.
          </p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <div className="field" style={{ marginBottom: 8 }}>
          <label>에이전트</label>
          <select value={agent} onChange={(event) => setAgent(event.target.value)}>
            {AGENTS.map((entry) => (
              <option key={entry.apiName} value={entry.apiName}>
                {entry.displayName} — {entry.description}
              </option>
            ))}
          </select>
        </div>
        <div className="actions">
          {PRESETS.map((preset) => (
            <button key={preset} className="ghost" onClick={() => send(preset)} disabled={invoke.isPending}>
              {preset}
            </button>
          ))}
        </div>
      </div>

      <div className="chat">
        <div className="chat-log">
          {turns.length === 0 && (
            <div className="empty">예시 문장을 눌러 에이전트를 실행해 보세요.</div>
          )}
          {turns.map((turn, index) => (
            <div key={index} className={`bubble ${turn.role === 'user' ? 'user' : ''}`}>
              {turn.text}
              {turn.proposals && turn.proposals.length > 0 && (
                <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                  → 제안 인박스에 {turn.proposals.length}건 등록됨
                </div>
              )}
              {turn.toolCalls && turn.toolCalls.length > 0 && (
                <details style={{ marginTop: 8 }}>
                  <summary className="muted" style={{ fontSize: 12, cursor: 'pointer' }}>
                    도구 호출 {turn.toolCalls.length}건 · 실행번호 {turn.runNo}
                  </summary>
                  {turn.toolCalls.map((call, callIndex) => (
                    <div key={callIndex} className={`tool-call ${call.isError ? 'error' : ''}`}>
                      {call.tool} {call.isError ? '✗' : '✓'} {call.result ? `— ${call.result.slice(0, 160)}` : ''}
                    </div>
                  ))}
                </details>
              )}
            </div>
          ))}
          {invoke.isPending && <div className="bubble muted">에이전트가 온톨로지를 조회하는 중…</div>}
        </div>

        <div className="chat-input">
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') send(input);
            }}
            placeholder="예: 행복식당 소주 5박스 내일 배송으로 접수해줘"
          />
          <button className="primary" onClick={() => send(input)} disabled={invoke.isPending}>
            실행
          </button>
        </div>
      </div>
    </>
  );
}
