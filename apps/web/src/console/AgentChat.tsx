import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { Markdown } from '../components/Markdown';
import type { AgentSummary, DomainApi, Envelope } from './api';

interface Turn {
  role: 'user' | 'assistant';
  text: string;
  toolCalls?: { tool: string; isError?: boolean; result?: string }[];
  proposals?: string[];
  runNo?: string;
}

/** Kept in sessionStorage so the log survives tab switches and reloads. */
const MAX_SAVED_TURNS = 50;

function storageKey(domainName: string): string {
  return `ontology-chat:${domainName}`;
}

/** Parse stored turns, discarding anything that does not look like a turn. */
function loadTurns(domainName: string): Turn[] {
  const raw = sessionStorage.getItem(storageKey(domainName));
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (entry): entry is Turn =>
        entry !== null &&
        typeof entry === 'object' &&
        (entry as Turn).role in { user: true, assistant: true } &&
        typeof (entry as Turn).text === 'string',
    );
  } catch {
    return [];
  }
}

function saveTurns(domainName: string, turns: Turn[]): void {
  try {
    const capped = turns.slice(-MAX_SAVED_TURNS);
    sessionStorage.setItem(storageKey(domainName), JSON.stringify(capped));
  } catch {
    // Quota or serialization failure must never break the chat itself.
  }
}

export interface AgentPreset {
  text: string;
  agent: string;
}

interface Props {
  api: DomainApi;
  domainName: string;
  presets?: AgentPreset[];
}

/** The agent a domain's chat opens on, preferring a copilot-style agent. */
function defaultAgent(agents: AgentSummary[], presets?: AgentPreset[]): string {
  const preferred = presets?.[0]?.agent;
  if (preferred && agents.some((entry) => entry.apiName === preferred)) return preferred;
  const copilot = agents.find((entry) => entry.kind === 'copilot');
  return copilot?.apiName ?? agents[0]?.apiName ?? '';
}

export function AgentChat({ api, domainName, presets }: Props) {
  const agentsQuery = useQuery({
    queryKey: [domainName, 'agents'],
    queryFn: () => api.agents(),
  });
  const agents = ((agentsQuery.data as Envelope<AgentSummary[]> | undefined)?.data ?? []).filter(
    (entry) => entry &&
    typeof entry === 'object',
  );

  const [agent, setAgent] = useState('');
  const [input, setInput] = useState('');
  const [turns, setTurns] = useState<Turn[]>(() => loadTurns(domainName));

  useEffect(() => {
    saveTurns(domainName, turns);
  }, [domainName, turns]);

  useEffect(() => {
    if (agents.length > 0 && !agents.some((entry) => entry.apiName === agent)) {
      setAgent(defaultAgent(agents, presets));
    }
  }, [agents, agent, presets]);

  const invoke = useMutation({
    // Pass the agent explicitly: setAgent is async, so relying on state here would
    // call the previously selected agent on the first click after a preset.
    mutationFn: ({ message, target }: { message: string; target: string }) =>
      api.invokeAgent(target, message),
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

  const send = (text: string, targetAgent = agent) => {
    const message = text.trim();
    if (!message || invoke.isPending || !targetAgent) return;
    setAgent(targetAgent);
    setTurns((current) => [...current, { role: 'user', text: message }]);
    setInput('');
    invoke.mutate({ message, target: targetAgent });
  };

  const activePresets = (presets ?? []).filter((preset) =>
    agents.some((entry) => entry.apiName === preset.agent),
  );

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

      {agents.length === 0 && !agentsQuery.isLoading && (
        <div className="empty">이 도메인에는 실행 가능한 에이전트가 없습니다.</div>
      )}

      {agents.length > 0 && (
        <>
          <div className="card" style={{ marginBottom: 14 }}>
            <div className="field" style={{ marginBottom: 8 }}>
              <label>에이전트</label>
              <select value={agent} onChange={(event) => setAgent(event.target.value)}>
                {agents.map((entry) => (
                  <option key={entry.apiName} value={entry.apiName}>
                    {entry.displayName} — {entry.description}
                  </option>
                ))}
              </select>
            </div>
            {activePresets.length > 0 && (
              <div className="actions">
                {activePresets.map((preset) => (
                  <button
                    key={preset.text}
                    className="ghost"
                    onClick={() => send(preset.text, preset.agent)}
                    disabled={invoke.isPending}
                  >
                    {preset.text}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="chat">
            {turns.length > 0 && (
              <div className="chat-toolbar">
                <button
                  className="ghost"
                  onClick={() => setTurns([])}
                  disabled={invoke.isPending}
                >
                  대화 지우기
                </button>
              </div>
            )}
            <div className="chat-log">
              {turns.length === 0 && (
                <div className="empty">
                  {activePresets.length > 0
                    ? '예시 문장을 눌러 에이전트를 실행해 보세요.'
                    : '메시지를 입력해 에이전트를 실행해 보세요.'}
                </div>
              )}
              {turns.map((turn, index) => (
                <div key={index} className={`bubble ${turn.role === 'user' ? 'user' : ''}`}>
                  {turn.role === 'assistant' ? <Markdown text={turn.text} /> : turn.text}
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
                          {call.tool} {call.isError ? '✗' : '✓'}{' '}
                          {call.result ? `— ${call.result.slice(0, 160)}` : ''}
                        </div>
                      ))}
                    </details>
                  )}
                </div>
              ))}
              {invoke.isPending && (
                <div className="bubble muted">에이전트가 온톨로지를 조회하는 중…</div>
              )}
            </div>

            <div className="chat-input">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') send(input);
                }}
                placeholder="메시지를 입력하세요"
              />
              <button
                className="primary"
                onClick={() => send(input)}
                disabled={invoke.isPending || !agent}
              >
                실행
              </button>
            </div>
          </div>
        </>
      )}
    </>
  );
}
