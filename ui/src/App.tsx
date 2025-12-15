import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Lobby from './components/Lobby';
import Dashboard from './components/Dashboard';

const queryClient = new QueryClient();

const App: React.FC = () => {
  const [selectedSession, setSelectedSession] = useState<string | null>(null);

  return (
    <QueryClientProvider client={queryClient}>
      <div>
        <h1>Dungeons & Dragons UI</h1>
        {!selectedSession ? (
          <Lobby onSelectSession={setSelectedSession} />
        ) : (
          <Dashboard sessionSlug={selectedSession} />
        )}
      </div>
    </QueryClientProvider>
  );
}

export default App;