import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

interface FileDiff {
  path: string;
  changes: string;
}

interface DiffViewerProps {
  sessionSlug: string;
}

const DiffViewer: React.FC<DiffViewerProps> = ({ sessionSlug }) => {
  const [fromCommit, setFromCommit] = useState('');
  const [toCommit, setToCommit] = useState('');
  const { data: diff, refetch } = useQuery({
    queryKey: ['diff', sessionSlug, fromCommit, toCommit],
    queryFn: () =>
      fetch(`/api/sessions/${sessionSlug}/diff?from=${fromCommit}&to=${toCommit}`).then(r => r.json()),
    enabled: false,
  });

  const handleViewDiff = () => {
    if (fromCommit && toCommit) {
      refetch();
    }
  };

  return (
    <div style={{ border: '1px solid #ccc', margin: '10px', padding: '10px' }}>
      <h3>Diff Viewer</h3>
      <div>
        <label>From commit: </label>
        <input
          type="text"
          value={fromCommit}
          onChange={(e) => setFromCommit(e.target.value)}
          placeholder="Commit ID"
        />
        <label>To commit: </label>
        <input
          type="text"
          value={toCommit}
          onChange={(e) => setToCommit(e.target.value)}
          placeholder="Commit ID"
        />
        <button onClick={handleViewDiff}>View Diff</button>
      </div>
      {diff && (
        <div>
          <h4>Diff</h4>
          {diff.files.map((file: FileDiff) => (
            <div key={file.path}>
              <strong>{file.path}</strong>
              <pre>{file.changes}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DiffViewer;
