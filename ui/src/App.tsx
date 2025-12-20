import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Lobby from './components/Lobby';
import Dashboard from './components/Dashboard';
import LLMConfig from './components/LLMConfig';

const queryClient = new QueryClient();

const App: React.FC = () => {
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [llmConfigUpdated, setLlmConfigUpdated] = useState(false);

  return (
    <QueryClientProvider client={queryClient}>
      <div>
        <h1>Dungeons & Dragons UI</h1>
        <LLMConfig onConfigSaved={() => setLlmConfigUpdated(!llmConfigUpdated)} />
        {!selectedSession ? (
          <Lobby onSelectSession={setSelectedSession} />
        ) : (
          <Dashboard sessionSlug={selectedSession} llmConfigUpdated={llmConfigUpdated} />
        )}
      </div>
    </QueryClientProvider>
  );
}

export default App;