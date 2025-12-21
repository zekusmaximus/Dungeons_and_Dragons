import React, { useEffect, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

interface TurnResponse {
  prompt: string;
  turn_number: number;
  lock_status: {
    owner: string;
    ttl: number;
    claimed_at: string;
  } | null;
}

interface PreviewResponse {
  id: string;
  diffs: { path: string; changes: string }[];
  entropy_plan: { indices: number[]; usage: string };
}

interface SessionState {
  hp?: number;
  location?: string;
  conditions?: string[];
  gp?: number;
  gold?: number;
  turn?: number;
  log_index?: number;
  [key: string]: any;
}

interface TurnConsoleProps {
  sessionSlug: string;
}

const TurnConsole: React.FC<TurnConsoleProps> = ({ sessionSlug }) => {
  const [response, setResponse] = useState('');
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [lastConsequence, setLastConsequence] = useState<string | null>(null);
  const [lastDiff, setLastDiff] = useState<string[]>([]);
  const lastSubmittedRef = useRef<string>('');
  const previousStateRef = useRef<SessionState | null>(null);
  const queryClient = useQueryClient();

  const { data: turnData, isLoading } = useQuery<TurnResponse>({
    queryKey: ['turn', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/turn`).then(r => r.json()),
  });

  const { data: stateData } = useQuery<SessionState>({
    queryKey: ['state', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/state`).then(r => r.json()),
  });

  useEffect(() => {
    if (stateData) {
      previousStateRef.current = stateData;
    }
  }, [stateData]);

  const summarizeDiff = (before: SessionState | null, after: SessionState): string[] => {
    if (!after) return [];
    if (!before) return ['State initialized'];
    const keys = new Set([...Object.keys(after || {}), ...Object.keys(before || {})]);
    const ignored = new Set(['turn', 'log_index']);
    const changes: string[] = [];
    keys.forEach((key) => {
      if (ignored.has(key)) return;
      const beforeVal = before[key];
      const afterVal = after[key];
      if (JSON.stringify(beforeVal) !== JSON.stringify(afterVal)) {
        changes.push(`${key}: ${JSON.stringify(beforeVal ?? '—')} -> ${JSON.stringify(afterVal ?? '—')}`);
      }
    });
    return changes;
  };

  const choiceScaffold = `Turn recap (one line):
- Location and situation:
- Danger / clock ticking:
- Resources: HP ${stateData?.hp ?? '?'} | Gold ${stateData?.gp ?? stateData?.gold ?? '?'} | Conditions ${stateData?.conditions?.join(', ') || 'none'}

Choices (2-4, include intent + risk):
1) [talk:risk-low] 
2) [sneak:risk-medium] 
3) [fight:risk-high] 
4) [investigate:risk-variable] 

Consequence echo: If the chosen path fails, introduce a complication instead of a dead-end.`;

  const claimLockMutation = useMutation({
    mutationFn: () => fetch(`/api/sessions/${sessionSlug}/lock/claim`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ owner: 'user1', ttl: 300 }),
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['turn', sessionSlug] }),
  });

  const releaseLockMutation = useMutation({
    mutationFn: () => fetch(`/api/sessions/${sessionSlug}/lock`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['turn', sessionSlug] }),
  });

  const previewMutation = useMutation({
    mutationFn: (res: string) => fetch(`/api/sessions/${sessionSlug}/turn/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ response: res }),
    }).then(r => r.json()),
    onMutate: (res) => {
      lastSubmittedRef.current = res;
      setLastConsequence(null);
      setLastDiff([]);
    },
    onSuccess: (data) => setPreview(data),
  });

  const commitMutation = useMutation({
    mutationFn: (previewId: string) => fetch(`/api/sessions/${sessionSlug}/turn/commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preview_id: previewId }),
    }).then(r => r.json()),
    onSuccess: (data) => {
      const nextState = data?.state as SessionState;
      const diffs = summarizeDiff(previousStateRef.current, nextState);
      setLastDiff(diffs);
      setLastConsequence(
        diffs.length
          ? `Because you answered "${lastSubmittedRef.current || 'this turn'}", ${diffs.join('; ')}`
          : 'Turn advanced without notable state changes. Consider adding consequences.'
      );
      previousStateRef.current = nextState;
      setPreview(null);
      setResponse('');
      queryClient.invalidateQueries();
    },
  });

  if (isLoading) return <div>Loading turn...</div>;

  const isLockedByMe = turnData?.lock_status?.owner === 'user1';
  const isLockedByOther = turnData?.lock_status && !isLockedByMe;

  return (
    <div className="turn-console">
      <style>{turnConsoleCSS}</style>
      <div className="turn-console__header">
        <h3>Turn Console</h3>
        <div className="turn-console__meta">
          <span>Turn {turnData?.turn_number}</span>
          <span>HP {stateData?.hp ?? '—'}</span>
          <span>Gold {stateData?.gp ?? stateData?.gold ?? 0}</span>
          <span>Location {stateData?.location || '—'}</span>
        </div>
      </div>

      <div className="prompt-box">
        <div className="prompt-label">
          Branch prompt {turnData?.lock_status ? `(locked by ${turnData.lock_status.owner})` : '(unlocked)'}
        </div>
        <pre>{turnData?.prompt}</pre>
      </div>

      <div className="guidance">
        <div className="guidance-title">Choice rules for this turn</div>
        <ul>
          <li>Offer 2–4 distinct options, each tagged with intent (talk / sneak / fight / magic / investigate).</li>
          <li>State the risk or cost attached to each option; failures should add pressure, not end the scene.</li>
          <li>Echo one new detail (rumor, clue, feature) every other turn to keep discovery flowing.</li>
        </ul>
      </div>

      <div className="action-row">
        {!turnData?.lock_status && (
          <button onClick={() => claimLockMutation.mutate()} className="primary">Claim Lock</button>
        )}
        {isLockedByMe && (
          <button onClick={() => releaseLockMutation.mutate()} className="ghost">Release Lock</button>
        )}
        <button
          className="ghost"
          onClick={() => setResponse((prev) => `${prev ? `${prev}\n` : ''}${choiceScaffold}`)}
          disabled={!!isLockedByOther}
        >
          Insert choice scaffold
        </button>
      </div>

      {isLockedByMe && (
        <div className="composer">
          <textarea
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            placeholder="Frame the recap, stakes, and 2–4 tagged options. End with a direct question."
            rows={7}
          />
          <div className="composer-actions">
            <button onClick={() => previewMutation.mutate(response)} disabled={!response.trim() || previewMutation.isPending} className="primary">
              {previewMutation.isPending ? 'Preparing preview...' : 'Preview turn'}
            </button>
          </div>
        </div>
      )}

      {preview && (
        <div className="preview-box">
          <div className="preview-header">
            <h4>Preview</h4>
            <div className="entropy">Entropy: {preview.entropy_plan.usage}</div>
          </div>
          <ul>
            {preview.diffs.map((diff, i) => (
              <li key={i}><strong>{diff.path}</strong>: {diff.changes}</li>
            ))}
          </ul>
          <div className="preview-actions">
            <button onClick={() => commitMutation.mutate(preview.id)} className="primary">
              {commitMutation.isPending ? 'Committing...' : 'Commit turn'}
            </button>
            <button onClick={() => setPreview(null)} className="ghost">Cancel</button>
          </div>
        </div>
      )}

      {lastConsequence && (
        <div className="consequence-box">
          <div className="consequence-title">Consequence echo</div>
          <div>{lastConsequence}</div>
          {lastDiff.length > 0 && (
            <ul>
              {lastDiff.map((d) => <li key={d}>{d}</li>)}
            </ul>
          )}
        </div>
      )}

      {isLockedByOther && <div className="warning">Session is locked by another user. Actions disabled.</div>}
    </div>
  );
};

const turnConsoleCSS = `
.turn-console {
  border: 2px solid #8B4513;
  border-radius: 8px;
  padding: 12px;
  background: #fdf7ef;
  box-shadow: 0 2px 4px rgba(0,0,0,0.08);
}

.turn-console__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
}

.turn-console__meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
}

.prompt-box {
  background: #fff;
  border: 1px solid #e3c9a7;
  border-radius: 6px;
  padding: 8px;
  margin: 10px 0;
}

.prompt-label {
  font-size: 12px;
  color: #8B4513;
  margin-bottom: 4px;
}

.guidance {
  background: #f6eddd;
  border: 1px solid #e3c9a7;
  border-radius: 6px;
  padding: 8px;
  font-size: 13px;
}

.guidance-title {
  font-weight: 700;
  margin-bottom: 4px;
}

.action-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 10px 0;
}

.composer textarea {
  width: 100%;
  border: 1px solid #d4b48d;
  border-radius: 6px;
  padding: 8px;
  font-family: inherit;
  background: #fff;
}

.composer-actions {
  margin-top: 6px;
  display: flex;
  justify-content: flex-end;
}

.primary, .ghost {
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #8B4513;
  cursor: pointer;
  font-weight: 600;
  background: #8B4513;
  color: #fff;
}

.ghost {
  background: transparent;
  color: #8B4513;
}

.preview-box {
  border: 1px solid #d4b48d;
  background: #fff;
  border-radius: 6px;
  padding: 8px;
  margin-top: 8px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.entropy {
  font-size: 12px;
  color: #555;
}

.preview-actions {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}

.consequence-box {
  margin-top: 10px;
  border-left: 3px solid #8B4513;
  padding-left: 8px;
  color: #4a3728;
  background: #fffaf3;
}

.consequence-title {
  font-weight: 700;
  margin-bottom: 4px;
}

.warning {
  color: #b00020;
  margin-top: 6px;
}
`;

export default TurnConsole;
