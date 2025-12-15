import React, { useState } from 'react';
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

interface TurnConsoleProps {
  sessionSlug: string;
}

const TurnConsole: React.FC<TurnConsoleProps> = ({ sessionSlug }) => {
  const [response, setResponse] = useState('');
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const queryClient = useQueryClient();

  const { data: turnData, isLoading } = useQuery({
    queryKey: ['turn', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/turn`).then(r => r.json()),
  });

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
    onSuccess: (data) => setPreview(data),
  });

  const commitMutation = useMutation({
    mutationFn: (previewId: string) => fetch(`/api/sessions/${sessionSlug}/turn/commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preview_id: previewId }),
    }).then(r => r.json()),
    onSuccess: () => {
      setPreview(null);
      setResponse('');
      queryClient.invalidateQueries();
    },
  });

  if (isLoading) return <div>Loading turn...</div>;

  const isLockedByMe = turnData?.lock_status?.owner === 'user1';
  const isLockedByOther = turnData?.lock_status && !isLockedByMe;

  return (
    <div style={{ border: '1px solid #ccc', margin: '10px', padding: '10px' }}>
      <h3>Turn Console</h3>
      <div>Turn: {turnData?.turn_number}</div>
      <div>Lock: {turnData?.lock_status ? `Locked by ${turnData.lock_status.owner}` : 'Unlocked'}</div>
      <pre>{turnData?.prompt}</pre>
      {!turnData?.lock_status && (
        <button onClick={() => claimLockMutation.mutate()}>Claim Lock</button>
      )}
      {isLockedByMe && (
        <button onClick={() => releaseLockMutation.mutate()}>Release Lock</button>
      )}
      {isLockedByMe && (
        <div>
          <textarea
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            placeholder="Enter your response"
            rows={5}
            cols={50}
          />
          <button onClick={() => previewMutation.mutate(response)}>Preview</button>
        </div>
      )}
      {preview && (
        <div>
          <h4>Preview</h4>
          <div>Entropy: {preview.entropy_plan.usage}</div>
          <ul>
            {preview.diffs.map((diff, i) => (
              <li key={i}>{diff.path}: {diff.changes}</li>
            ))}
          </ul>
          <button onClick={() => commitMutation.mutate(preview.id)}>Commit</button>
          <button onClick={() => setPreview(null)}>Cancel</button>
        </div>
      )}
      {isLockedByOther && <div style={{ color: 'red' }}>Session is locked by another user. Actions disabled.</div>}
    </div>
  );
};

export default TurnConsole;