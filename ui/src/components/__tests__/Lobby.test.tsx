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
  global.fetch = jest.fn((url: RequestInfo | URL) =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve([]),
    } as unknown as Response)
  );

  renderWithClient(<Lobby onSelectSession={mockOnSelect} onNewAdventure={jest.fn()} />);

  expect(await screen.findByText(/Solo Adventure Lobby/)).toBeInTheDocument();
  expect(await screen.findByText('Your Adventures')).toBeInTheDocument();
  expect(screen.getByText('No existing adventures found.')).toBeInTheDocument();
});
