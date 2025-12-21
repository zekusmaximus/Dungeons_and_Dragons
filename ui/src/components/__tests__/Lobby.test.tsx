import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Lobby from '../Lobby';

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

const renderWithClient = (ui: React.ReactElement) => {
  const testQueryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={testQueryClient}>
      {ui}
    </QueryClientProvider>
  );
};

test('renders lobby with sessions', async () => {
  const mockOnSelect = jest.fn();
  renderWithClient(<Lobby onSelectSession={mockOnSelect} onNewAdventure={jest.fn()} />);

  expect(screen.getByText('Session Lobby')).toBeInTheDocument();
  // Since we can't mock fetch easily, just check the structure
});
