import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import JobsDrawer from '../JobsDrawer';

declare const global: any;

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

test('renders jobs drawer and creates job', async () => {
  // Mock fetch
  global.fetch = jest.fn();

  renderWithClient(<JobsDrawer sessionSlug="test-session" />);

  expect(screen.getByText('Open Jobs Drawer')).toBeInTheDocument();

  fireEvent.click(screen.getByText('Open Jobs Drawer'));

  expect(screen.getByText('Jobs')).toBeInTheDocument();
  expect(screen.getByText('Create New Job')).toBeInTheDocument();

  // Mock create job response
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    json: () => Promise.resolve({ id: 'job-1', type: 'explore', status: 'running' }),
  });

  fireEvent.click(screen.getByText('Explore'));

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/jobs/explore', expect.any(Object));
  });
});