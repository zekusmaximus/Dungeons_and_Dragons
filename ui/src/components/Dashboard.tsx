import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import TurnConsole from './TurnConsole';
import JobsDrawer from './JobsDrawer';
import CommitTimeline from './CommitTimeline';
import DiffViewer from './DiffViewer';
import LiveUpdates from './LiveUpdates';
import ExportBundle from './ExportBundle';

interface DashboardProps {
  sessionSlug: string;
}

const Dashboard: React.FC<DashboardProps> = ({ sessionSlug }) => {
  const [liveLockOwner, setLiveLockOwner] = useState<string | null>(null);
  const [liveTranscriptTail, setLiveTranscriptTail] = useState<string[]>([]);

  const { data: turnData } = useQuery({
    queryKey: ['turn', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/turn`).then(r => r.json()),
  });

  const lockOwner = liveLockOwner || turnData?.lock_status?.owner;
  const isLockedByOther = lockOwner && lockOwner !== 'user1';

  return (
    <div>
      <h2>Dashboard for {sessionSlug}</h2>
      {isLockedByOther && (
        <div style={{ background: 'red', color: 'white', padding: '10px', margin: '10px' }}>
          Session is locked by {lockOwner}. Actions are disabled.
        </div>
      )}
      <LiveUpdates
        sessionSlug={sessionSlug}
        onTranscriptUpdate={setLiveTranscriptTail}
        onLockUpdate={setLiveLockOwner}
      />
      <TurnConsole sessionSlug={sessionSlug} />
      <JobsDrawer sessionSlug={sessionSlug} />
      <StatePanel sessionSlug={sessionSlug} />
      <TranscriptPanel sessionSlug={sessionSlug} liveTail={liveTranscriptTail} />
      <ChangelogPanel sessionSlug={sessionSlug} />
      <QuestsPanel sessionSlug={sessionSlug} />
      <NpcMemoryPanel sessionSlug={sessionSlug} />
      <WorldPanel sessionSlug={sessionSlug} />
      <EntropyPanel />
      <CommitTimeline sessionSlug={sessionSlug} />
      <DiffViewer sessionSlug={sessionSlug} />
      <ExportBundle sessionSlug={sessionSlug} />
    </div>
  );
};

const StatePanel: React.FC<{ sessionSlug: string }> = ({ sessionSlug }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['state', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/state`).then(r => r.json()),
  });
  return <Panel title="State" data={data} isLoading={isLoading} />;
};

const TranscriptPanel: React.FC<{ sessionSlug: string; liveTail?: string[] }> = ({ sessionSlug, liveTail }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['transcript', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/transcript`).then(r => r.json()),
  });
  const combinedData = [...(data?.items || []), ...(liveTail || [])];
  return <Panel title="Transcript" data={combinedData} isLoading={isLoading} />;
};

const ChangelogPanel: React.FC<{ sessionSlug: string }> = ({ sessionSlug }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['changelog', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/changelog`).then(r => r.json()),
  });
  return <Panel title="Changelog" data={data?.items} isLoading={isLoading} />;
};

const QuestsPanel: React.FC<{ sessionSlug: string }> = ({ sessionSlug }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['quests', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/quests`).then(r => r.json()),
  });
  return <Panel title="Quests" data={data?.quests} isLoading={isLoading} />;
};

const NpcMemoryPanel: React.FC<{ sessionSlug: string }> = ({ sessionSlug }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['npc-memory', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/npc-memory`).then(r => r.json()),
  });
  return <Panel title="NPC Memory" data={data?.npc_memory} isLoading={isLoading} />;
};

const WorldPanel: React.FC<{ sessionSlug: string }> = ({ sessionSlug }) => {
  const { data: factions } = useQuery({
    queryKey: ['factions', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/world/factions`).then(r => r.json()),
  });
  const { data: timeline } = useQuery({
    queryKey: ['timeline', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/world/timeline`).then(r => r.json()),
  });
  const { data: rumors } = useQuery({
    queryKey: ['rumors', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/world/rumors`).then(r => r.json()),
  });
  const { data: factionClocks } = useQuery({
    queryKey: ['faction-clocks', sessionSlug],
    queryFn: () => fetch(`/api/sessions/${sessionSlug}/world/faction-clocks`).then(r => r.json()),
  });
  return (
    <div>
      <h3>World</h3>
      <Panel title="Factions" data={factions} />
      <Panel title="Timeline" data={timeline} />
      <Panel title="Rumors" data={rumors} />
      <Panel title="Faction Clocks" data={factionClocks} />
    </div>
  );
};

const EntropyPanel: React.FC = () => {
  const { data, isLoading } = useQuery({
    queryKey: ['entropy'],
    queryFn: () => fetch('/api/entropy').then(r => r.json()),
  });
  return <Panel title="Entropy" data={data?.entropy} isLoading={isLoading} />;
};

const Panel: React.FC<{ title: string; data?: any; isLoading?: boolean }> = ({ title, data, isLoading }) => (
  <div style={{ border: '1px solid #ccc', margin: '10px', padding: '10px' }}>
    <h3>{title}</h3>
    {isLoading ? <div>Loading...</div> : <pre>{JSON.stringify(data, null, 2)}</pre>}
  </div>
);

export default Dashboard;
