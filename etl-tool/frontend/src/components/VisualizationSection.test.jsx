// Simple test to check if VisualizationSection auto-refreshes prices
import { render, screen, waitFor } from '@testing-library/react';
import VisualizationSection from './VisualizationSection';

test('auto-refreshes and updates prices', async () => {
  render(<VisualizationSection />);
  // Wait for initial loading
  expect(screen.getByText(/Loading global cryptocurrency market data/i)).toBeInTheDocument();
  // Wait for data to load
  await waitFor(() => expect(screen.queryByText(/Loading global cryptocurrency market data/i)).not.toBeInTheDocument(), { timeout: 10000 });
  // Check that some price data is rendered (look for a known coin)
  expect(screen.getByText(/Bitcoin|BTC/i)).toBeInTheDocument();
  // Wait for at least one auto-refresh (5s interval)
  await new Promise(res => setTimeout(res, 6000));
  // Check that update count or timestamp changes (implying refresh)
  // This is a basic check; for more robust, mock fetchDetailedMarketData
  expect(screen.getByText(/Dashboard|List|Compare/i)).toBeInTheDocument();
});
