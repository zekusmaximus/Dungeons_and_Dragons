import React, { useState, useEffect } from 'react';
import SchemaForm from './SchemaForm';

interface QuestEditorProps {
  sessionSlug: string;
  questId?: string;
}

const QuestEditor: React.FC<QuestEditorProps> = ({ sessionSlug, questId }) => {
  const [data, setData] = useState<Record<string, any>>({});
  const [schema, setSchema] = useState<any>({});
  const [preview, setPreview] = useState<any>(null);
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    // Fetch schema
    fetch('/api/schemas/quest.schema.json')
      .then(res => res.json())
      .then(setSchema);

    if (questId) {
      // Fetch existing quest
      fetch(`/api/sessions/${sessionSlug}/quests/${questId}`)
        .then(res => res.json())
        .then(setData);
    }
  }, [sessionSlug, questId]);

  const handlePreview = () => {
    const url = questId
      ? `/api/sessions/${sessionSlug}/quests/${questId}?dry_run=true`
      : `/api/sessions/${sessionSlug}/quests?dry_run=true`;
    fetch(url, {
      method: questId ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
      .then(res => res.json())
      .then((res) => {
        if (res.errors) {
          setErrors(res.errors);
        } else {
          setPreview(res);
          setErrors([]);
        }
      });
  };

  const handleCommit = () => {
    const url = questId
      ? `/api/sessions/${sessionSlug}/quests/${questId}`
      : `/api/sessions/${sessionSlug}/quests`;
    fetch(url, {
      method: questId ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
      .then(() => alert('Saved'));
  };

  return (
    <div>
      <h2>{questId ? 'Edit Quest' : 'Create Quest'}</h2>
      <SchemaForm
        schema={schema}
        data={data}
        onChange={setData}
        onSubmit={handlePreview}
        errors={errors}
      />
      {preview && (
        <div>
          <h3>Preview</h3>
          <pre>{JSON.stringify(preview, null, 2)}</pre>
          <button onClick={handleCommit}>Commit</button>
        </div>
      )}
    </div>
  );
};

export default QuestEditor;