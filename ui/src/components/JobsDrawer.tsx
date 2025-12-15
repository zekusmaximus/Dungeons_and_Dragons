import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';

interface JobsDrawerProps {
  sessionSlug: string;
}

interface Job {
  id: string;
  type: string;
  status: string;
  created_at: string;
  params: Record<string, any>;
}

const JobsDrawer: React.FC<JobsDrawerProps> = ({ sessionSlug }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [currentJob, setCurrentJob] = useState<Job | null>(null);
  const [jobParams, setJobParams] = useState<Record<string, any>>({ slug: sessionSlug });

  const { data: progress } = useQuery({
    queryKey: ['job-progress', currentJob?.id],
    queryFn: () => currentJob ? fetch(`/api/jobs/${currentJob.id}`).then(r => r.json()) : null,
    enabled: !!currentJob,
    refetchInterval: currentJob?.status === 'running' ? 1000 : false,
  });

  const createJobMutation = useMutation({
    mutationFn: (data: { type: string; params: Record<string, any> }) =>
      fetch(`/api/jobs/${data.type}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: data.type, params: data.params }),
      }).then(r => r.json()),
    onSuccess: (job: Job) => {
      setCurrentJob(job);
      setIsOpen(true);
    },
  });

  const commitMutation = useMutation({
    mutationFn: (jobId: string) =>
      fetch(`/api/jobs/${jobId}/commit`, { method: 'POST' }),
    onSuccess: () => {
      setCurrentJob(null);
      setIsOpen(false);
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (jobId: string) =>
      fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' }),
    onSuccess: () => {
      setCurrentJob(null);
      setIsOpen(false);
    },
  });

  const handleCreateJob = (type: string) => {
    createJobMutation.mutate({ type, params: jobParams });
  };

  const handleParamChange = (key: string, value: string) => {
    setJobParams(prev => ({ ...prev, [key]: value }));
  };

  return (
    <>
      <button onClick={() => setIsOpen(true)} style={{ margin: '10px' }}>
        Open Jobs Drawer
      </button>

      {isOpen && (
        <div style={{
          position: 'fixed',
          top: 0,
          right: 0,
          width: '400px',
          height: '100%',
          background: 'white',
          borderLeft: '1px solid #ccc',
          padding: '20px',
          overflowY: 'auto',
          zIndex: 1000,
        }}>
          <button onClick={() => setIsOpen(false)} style={{ float: 'right' }}>X</button>
          <h3>Jobs</h3>

          {!currentJob ? (
            <div>
              <h4>Create New Job</h4>
              <div>
                <label>Steps: <input type="number" onChange={e => handleParamChange('steps', e.target.value)} /></label>
              </div>
              <div>
                <label>Pace: 
                  <select onChange={e => handleParamChange('pace', e.target.value)}>
                    <option>slow</option>
                    <option>normal</option>
                    <option>fast</option>
                  </select>
                </label>
              </div>
              <button onClick={() => handleCreateJob('explore')}>Explore</button>
              <button onClick={() => handleCreateJob('resolve-encounter')}>Resolve Encounter</button>
              <button onClick={() => handleCreateJob('loot')}>Loot</button>
              <button onClick={() => handleCreateJob('downtime')}>Downtime</button>
              <div>
                <label>Template: <input onChange={e => handleParamChange('template', e.target.value)} /></label>
                <button onClick={() => handleCreateJob('quest/init')}>Quest Init</button>
              </div>
            </div>
          ) : (
            <div>
              <h4>Job Progress: {currentJob.type}</h4>
              <p>Status: {progress?.status}</p>
              {progress?.error && <p style={{ color: 'red' }}>Error: {progress.error}</p>}
              <div>
                <h5>Logs</h5>
                <pre style={{ maxHeight: '200px', overflowY: 'auto' }}>
                  {progress?.logs.join('\n')}
                </pre>
              </div>
              <div>
                <h5>Entropy Usage</h5>
                <p>{progress?.entropy_usage.join(', ')}</p>
              </div>
              <div>
                <h5>Diff Preview</h5>
                <ul>
                  {progress?.diff_preview.map((diff: { path: string; changes: string }, i: number) => (
                    <li key={i}>{diff.path}: {diff.changes}</li>
                  ))}
                </ul>
              </div>
              {progress?.status === 'completed' && (
                <div>
                  <button onClick={() => commitMutation.mutate(currentJob.id)}>Commit</button>
                  <button onClick={() => cancelMutation.mutate(currentJob.id)}>Cancel</button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
};

export default JobsDrawer;