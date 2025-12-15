import React from 'react';

interface ExportBundleProps {
  sessionSlug: string;
}

const ExportBundle: React.FC<ExportBundleProps> = ({ sessionSlug }) => {
  const handleExport = async () => {
    const [state, transcript, changelog, journal] = await Promise.all([
      fetch(`/api/sessions/${sessionSlug}/state`).then(r => r.json()),
      fetch(`/api/sessions/${sessionSlug}/transcript`).then(r => r.json()),
      fetch(`/api/sessions/${sessionSlug}/changelog`).then(r => r.json()),
      fetch(`/api/sessions/${sessionSlug}/journal`).then(r => r.json()), // Assuming journal endpoint exists
    ]);

    const bundle = {
      state,
      transcript: transcript.items,
      changelog: changelog.items,
      journal,
    };

    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${sessionSlug}-bundle.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ border: '1px solid #ccc', margin: '10px', padding: '10px' }}>
      <h3>Export Session Bundle</h3>
      <button onClick={handleExport}>Download Bundle</button>
    </div>
  );
};

export default ExportBundle;