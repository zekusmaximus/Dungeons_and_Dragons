import React, { useEffect, useState } from 'react';
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

interface DMChoice {
  id: string;
  text: string;
  intent_tag: string;
  risk: string;
}

interface DiscoveryItem {
  title: string;
  text: string;
}

interface DMNarration {
  narration: string;
  recap: string;
  stakes: string;
  choices: DMChoice[];
  discovery_added?: DiscoveryItem;
}

interface TurnRecord {
  turn: number;
  player_intent: string;
  diff: string[];
  consequence_echo: string;
  dm: DMNarration;
  created_at: string;
}

interface CommitAndNarrateResponse {
  commit: { state: SessionState; log_indices: { transcript: number; changelog: number } };
  dm: DMNarration;
  turn_record: TurnRecord;
  usage: Record<string, number> | null;
}

interface TurnConsoleProps {
  sessionSlug: string;
}

const TurnConsole: React.FC<TurnConsoleProps> = ({ sessionSlug }) => {
  const [response, setResponse] = useState('');
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [lastConsequence, setLastConsequence] = useState<string | null>(null);
  const [lastDiff, setLastDiff] = useState<string[]>([]);
  const [dmOutput, setDmOutput] = useState<DMNarration | null>(null);
  const queryClient = useQueryClient();

  const { data: turnData, isLoading } = useQuery<TurnResponse>({
    queryKey: ['turn', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/turn`).then(r => r.json()),
  });

  const { data: stateData } = useQuery<SessionState>({
    queryKey: ['state', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/state`).then(r => r.json()),
  });

  const { data: turnRecords } = useQuery<TurnRecord[]>({
    queryKey: ['turn-records', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/turns?limit=3`).then(r => r.json()),
  });

  useEffect(() => {
    if (turnRecords && turnRecords.length > 0) {
      setDmOutput(turnRecords[0].dm);
      setLastConsequence(turnRecords[0].consequence_echo);
      setLastDiff(turnRecords[0].diff);
    }
  }, [turnRecords]);

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
    onMutate: () => {
      setLastConsequence(null);
      setLastDiff([]);
    },
    onSuccess: (data) => setPreview(data),
  });

  const commitMutation = useMutation({
    mutationFn: (previewId: string) => fetch(`/api/sessions/${sessionSlug}/turn/commit-and-narrate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preview_id: previewId }),
    }).then(r => r.json()),
    onSuccess: (data: CommitAndNarrateResponse) => {
      setDmOutput(data.dm);
      setLastDiff(data.turn_record.diff || []);
      setLastConsequence(data.turn_record.consequence_echo || null);
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

      <div className="turn-console__body">
        <div className="turn-console__main">
          <div className="prompt-box">
            <div className="prompt-label">
              Branch prompt {turnData?.lock_status ? `(locked by ${turnData.lock_status.owner})` : '(unlocked)'}
            </div>
            <pre>{turnData?.prompt}</pre>
          </div>

          {dmOutput && (
            <div className="dm-output">
              <div className="dm-output__header">
                <div>
                  <div className="dm-output__title">DM Narration</div>
                  <div className="dm-output__stakes">{dmOutput.stakes}</div>
                </div>
              </div>
              <p className="dm-output__narration">{dmOutput.narration}</p>
              <div className="dm-output__recap"><strong>Recap:</strong> {dmOutput.recap}</div>
              {dmOutput.discovery_added && (
                <div className="dm-output__discovery">
                  <div className="discovery-label">Discovery</div>
                  <div className="discovery-title">{dmOutput.discovery_added.title}</div>
                  <div className="discovery-text">{dmOutput.discovery_added.text}</div>
                </div>
              )}
              <div className="dm-output__choices">
                {dmOutput.choices.map((choice) => (
                  <button
                    key={choice.id}
                    className="choice-chip"
                    onClick={() => setResponse(choice.text)}
                    title={`${choice.intent_tag} • ${choice.risk} risk`}
                  >
                    <span className="choice-id">{choice.id}</span>
                    <span className="choice-text">{choice.text}</span>
                    <span className="choice-meta">{choice.intent_tag} • {choice.risk} risk</span>
                  </button>
                ))}
              </div>
            </div>
          )}

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

        <div className="turn-console__sidebar">
          <div className="recap-box">
            <div className="recap-title">Recap last 3 turns</div>
            {!turnRecords || turnRecords.length === 0 ? (
              <div className="recap-empty">No turns recorded yet.</div>
            ) : (
              <ul className="recap-list">
                {turnRecords.map((record) => (
                  <li key={record.turn} className="recap-item">
                    <div className="recap-turn">Turn {record.turn}</div>
                    <div className="recap-echo">{record.consequence_echo}</div>
                    {record.diff && record.diff.length > 0 && (
                      <div className="recap-diff">{record.diff.slice(0, 2).join(' | ')}</div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
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

.turn-console__body {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 12px;
}

.turn-console__main {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.turn-console__sidebar {
  background: #fffaf3;
  border: 1px solid #e3c9a7;
  border-radius: 6px;
  padding: 10px;
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

.dm-output {
  border: 1px solid #d4b48d;
  background: #fff;
  border-radius: 6px;
  padding: 10px;
}

.dm-output__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.dm-output__title {
  font-weight: 700;
  color: #8B4513;
}

.dm-output__stakes {
  font-size: 12px;
  color: #5a4634;
}

.dm-output__narration {
  margin: 6px 0;
  line-height: 1.5;
}

.dm-output__recap {
  font-size: 13px;
  color: #4a3728;
}

.dm-output__discovery {
  margin-top: 8px;
  padding: 8px;
  border: 1px dashed #d4b48d;
  border-radius: 6px;
  background: #fff9f0;
}

.discovery-label {
  font-weight: 700;
  font-size: 12px;
  color: #8B4513;
}

.discovery-title {
  font-weight: 700;
}

.dm-output__choices {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 6px;
}

.choice-chip {
  border: 1px solid #d4b48d;
  background: #fdf7ef;
  border-radius: 6px;
  padding: 8px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s;
}

.choice-chip:hover {
  border-color: #8B4513;
  background: #fff;
}

.choice-id {
  font-weight: 700;
  margin-right: 6px;
}

.choice-text {
  display: block;
}

.choice-meta {
  font-size: 12px;
  color: #5a4634;
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

.recap-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recap-title {
  font-weight: 700;
  color: #8B4513;
}

.recap-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recap-item {
  border: 1px solid #e3c9a7;
  border-radius: 6px;
  padding: 8px;
  background: #fff;
}

.recap-turn {
  font-weight: 700;
}

.recap-echo {
  font-size: 13px;
  margin-top: 4px;
}

.recap-diff {
  font-size: 12px;
  color: #5a4634;
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
