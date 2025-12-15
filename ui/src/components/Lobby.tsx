import React from 'react';
import { useQuery } from '@tanstack/react-query';

interface SessionSummary {
  slug: string;
  world: string;
  has_lock: boolean;
  updated_at: number;
}

const fetchSessions = async (): Promise<SessionSummary[]> => {
  const response = await fetch('/api/sessions');
  if (!response.ok) throw new Error('Failed to fetch sessions');
  return response.json();
};

interface LobbyProps {
  onSelectSession: (slug: string) => void;
}

const Lobby: React.FC<LobbyProps> = ({ onSelectSession }) => {
  const { data: sessions, isLoading, error } = useQuery({
    queryKey: ['sessions'],
    queryFn: fetchSessions,
  });

  if (isLoading) return <div>Loading sessions...</div>;
  if (error) return <div>Error loading sessions</div>;

  return (
    <div>
      <h2>Session Lobby</h2>
      <ul>
        {sessions?.map((session) => (
          <li key={session.slug}>
            <button onClick={() => onSelectSession(session.slug)}>
              {session.slug} - {session.world} {session.has_lock ? '(Locked)' : ''} - Updated: {new Date(session.updated_at * 1000).toLocaleString()}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default Lobby;