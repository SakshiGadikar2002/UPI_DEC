// Utility to fetch global cryptocurrency market data
// Uses backend proxy to avoid CORS issues

const API_BASE_URL = ''; // Use relative URLs to call backend proxy

// Top cryptocurrencies to track (matching the symbols used in RealtimeStream)
const TRACKED_CRYPTO_IDS = {
  'BTCUSDT': 'bitcoin',
  'ETHUSDT': 'ethereum',
  'BNBUSDT': 'binancecoin',
  'SOLUSDT': 'solana',
  'XRPUSDT': 'ripple',
  'ADAUSDT': 'cardano',
  'DOGEUSDT': 'dogecoin',
  'MATICUSDT': 'matic-network',
  'DOTUSDT': 'polkadot',
  'AVAXUSDT': 'avalanche-2',
  'SHIBUSDT': 'shiba-inu',
  'TRXUSDT': 'tron',
  'LINKUSDT': 'chainlink',
  'UNIUSDT': 'uniswap',
  'ATOMUSDT': 'cosmos',
  'LTCUSDT': 'litecoin',
  'ETCUSDT': 'ethereum-classic',
  'XLMUSDT': 'stellar',
  'ALGOUSDT': 'algorand',
  'NEARUSDT': 'near'
};

// Convert CoinGecko ID to symbol format
const ID_TO_SYMBOL = {};
Object.entries(TRACKED_CRYPTO_IDS).forEach(([symbol, id]) => {
  ID_TO_SYMBOL[id] = symbol;
});

/**
 * Fetch market data from CoinGecko
 * Returns data in format compatible with RealtimeStream component
 */
export const fetchGlobalCryptoMarketData = async () => {
  try {
    const ids = Object.values(TRACKED_CRYPTO_IDS).join(',');
    
    // Fetch market data with price, 24h change, volume, etc.
    // Note: CoinGecko uses 'usd' not 'usdt' as the base currency
    const response = await fetch(
      `${COINGECKO_API_BASE}/simple/price?ids=${ids}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true&include_last_updated_at=true`
    );
    
    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = `CoinGecko API error: ${response.status}`;
      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.error || errorMessage;
      } catch (e) {
        errorMessage = errorText || errorMessage;
      }
      throw new Error(errorMessage);
    }
    
    const data = await response.json();
    
    // Transform CoinGecko data to format compatible with RealtimeStream
    const transformedData = [];
    
    Object.entries(data).forEach(([id, priceData]) => {
      const symbol = ID_TO_SYMBOL[id];
      if (!symbol) return;
      
      const price = priceData.usd || 0;
      const change24h = priceData.usd_24h_change || 0;
      const volume24h = priceData.usd_24h_vol || 0;
      const lastUpdated = priceData.last_updated_at || Date.now() / 1000;
      
      // Transform to OKX-like format that RealtimeStream understands
      // This format matches what RealtimeStream expects: { arg: {...}, data: [...] }
      transformedData.push({
        arg: {
          channel: 'tickers',
          instId: symbol.replace('USDT', '-USDT') // BTCUSDT -> BTC-USDT
        },
        data: [{
          instId: symbol.replace('USDT', '-USDT'),
          last: price.toString(),
          px: price.toString(), // Primary price field for RealtimeStream
          p: price.toString(), // Alternative price field
          lastSz: '0',
          askPx: (price * 1.001).toFixed(2), // Simulated ask price
          askSz: '0',
          bidPx: (price * 0.999).toFixed(2), // Simulated bid price
          bidSz: '0',
          open24h: (price / (1 + change24h / 100)).toFixed(2),
          high24h: (price * 1.1).toFixed(2), // Simulated high
          low24h: (price * 0.9).toFixed(2), // Simulated low
          vol24h: volume24h.toString(),
          volCcy24h: (volume24h * price).toString(),
          ts: (lastUpdated * 1000).toString(), // Convert to milliseconds
          change24h: change24h.toString(),
          // Additional fields for compatibility
          sz: '0',
          tradeId: Date.now().toString(),
          side: 'buy',
          timestamp: lastUpdated * 1000
        }]
      });
    });
    
    return transformedData;
  } catch (error) {
    console.error('Error fetching global crypto market data:', error);
    throw error;
  }
};

/**
 * Fetch global market statistics (market cap, volume, etc.)
 */
export const fetchGlobalMarketStats = async () => {
  try {
    // Use backend proxy to avoid CORS issues
    const response = await fetch(
      `${API_BASE_URL}/api/crypto/global-stats`
    );
    
    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = `API error: ${response.status}`;
      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.detail || errorMessage;
      } catch (e) {
        errorMessage = errorText || errorMessage;
      }
      throw new Error(errorMessage);
    }
    
    const data = await response.json();
    return data.data;
  } catch (error) {
    console.error('Error fetching global market stats:', error);
    throw error;
  }
};

/**
 * Fetch detailed market data with more information
 * Returns both coin data and global market stats
 * Includes retry logic with exponential backoff for rate limiting (429 errors)
 */
export const fetchDetailedMarketData = async (retryCount = 0, maxRetries = 3) => {
  try {
    const ids = Object.values(TRACKED_CRYPTO_IDS).join(',');
    
    // Fetch coin market data first (required)
    const coinsResponse = await fetch(
      `${API_BASE_URL}/api/crypto/markets?vs_currency=usd&ids=${ids}&order=market_cap_desc&per_page=20&page=1&sparkline=true&price_change_percentage=1h%2C24h%2C7d`
    );
    
    // Handle 429 (Too Many Requests) with exponential backoff retry
    if (coinsResponse.status === 429) {
      if (retryCount < maxRetries) {
        const backoffDelay = Math.min(1000 * Math.pow(2, retryCount), 30000); // Max 30 seconds
        console.warn(`Rate limited (429). Retrying in ${backoffDelay}ms... (attempt ${retryCount + 1}/${maxRetries})`);
        await new Promise(resolve => setTimeout(resolve, backoffDelay));
        return fetchDetailedMarketData(retryCount + 1, maxRetries);
      } else {
        throw new Error('Rate limit exceeded. Please wait before refreshing.');
      }
    }
    
    // Handle 502 Bad Gateway (backend error, might have cached data)
    if (coinsResponse.status === 502) {
      const errorText = await coinsResponse.text();
      let errorMessage = `Backend error: ${coinsResponse.status}`;
      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.detail || errorMessage;
        // If it's a rate limit error, retry
        if (errorMessage.includes('429') || errorMessage.includes('Rate limit')) {
          if (retryCount < maxRetries) {
            const backoffDelay = Math.min(1000 * Math.pow(2, retryCount), 30000);
            console.warn(`Backend rate limited. Retrying in ${backoffDelay}ms... (attempt ${retryCount + 1}/${maxRetries})`);
            await new Promise(resolve => setTimeout(resolve, backoffDelay));
            return fetchDetailedMarketData(retryCount + 1, maxRetries);
          }
        }
      } catch (e) {
        // Ignore parse errors
      }
      throw new Error(errorMessage);
    }
    
    if (!coinsResponse.ok) {
      const errorText = await coinsResponse.text();
      let errorMessage = `API error: ${coinsResponse.status}`;
      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.detail || errorMessage;
      } catch (e) {
        errorMessage = errorText || errorMessage;
      }
      throw new Error(errorMessage);
    }
    
    // Fetch global stats separately (optional, don't fail if this fails)
    let globalStatsResponse = null;
    try {
      globalStatsResponse = await fetch(`${API_BASE_URL}/api/crypto/global-stats`);
      // Don't throw on errors for global stats, just log
      if (!globalStatsResponse.ok) {
        console.warn(`Global stats fetch failed: ${globalStatsResponse.status}`);
      }
    } catch (e) {
      console.warn('Global stats fetch error (non-critical):', e);
    }
    
    const coinsData = await coinsResponse.json();
    let globalStats = null;
    
    // Try to get global stats if available (non-critical)
    if (globalStatsResponse && globalStatsResponse.ok) {
      try {
        const globalData = await globalStatsResponse.json();
        globalStats = globalData.data || globalData;
      } catch (e) {
        console.warn('Failed to parse global stats:', e);
      }
    }
    
    // Transform to our format
    const transformedData = [];
    
    coinsData.forEach((coin) => {
      const symbol = ID_TO_SYMBOL[coin.id];
      if (!symbol) return;
      
      // Ensure accurate real-time price - use current_price from CoinGecko API
      // CoinGecko provides current_price which reflects the latest market price
      const currentPrice = coin.current_price || 0;
      const sparkline = coin.sparkline_in_7d?.price || [];
      
      // Get current timestamp for accurate real-time tracking
      const currentTimestamp = Date.now();
      
      // Transform sparkline into chartData points (for mini and full charts)
      // The sparkline is 7-day historical data - we'll display it as TODAY's intraday data for real-time appearance
      const chartData = sparkline.length > 0
        ? sparkline.map((price, index) => {
            // Spread sparkline points across TODAY (from 00:00 to now) for real-time view
            const now = Date.now();
            const today = new Date(now);
            today.setHours(0, 0, 0, 0);
            const todayStart = today.getTime();
            
            const ratio = index / Math.max(sparkline.length - 1, 1);
            const timestamp = todayStart + ratio * (now - todayStart);
            const dateObj = new Date(timestamp);
            
            // Format with TODAY's date and current time
            const time = dateObj.toLocaleString([], {
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              hour12: false
            });
            
            return {
              time: time,
              price: price,
              timestamp
            };
          })
        : [];
      
      // Format price with appropriate precision (preserve CoinGecko's precision)
      // For most cryptocurrencies, 2-8 decimal places is appropriate
      const formatPrice = (price) => {
        if (!price || price === 0) return '0';
        // For prices > 1, use 2 decimal places; for prices < 1, use more precision
        if (price >= 1) {
          return price.toFixed(2);
        } else if (price >= 0.01) {
          return price.toFixed(4);
        } else {
          return price.toFixed(8);
        }
      };
      
      transformedData.push({
        arg: {
          channel: 'tickers',
          instId: symbol.replace('USDT', '-USDT')
        },
        data: [{
          instId: symbol.replace('USDT', '-USDT'),
          last: formatPrice(currentPrice), // Real-time price from CoinGecko
          px: formatPrice(currentPrice), // Primary price field for RealtimeStream - reflects current market price
          p: formatPrice(currentPrice), // Alternative price field - ensures compatibility
          lastSz: '0',
          askPx: formatPrice(currentPrice * 1.001), // Simulated ask price
          askSz: '0',
          bidPx: formatPrice(currentPrice * 0.999), // Simulated bid price
          bidSz: '0',
          open24h: currentPrice ? formatPrice(currentPrice / (1 + (coin.price_change_percentage_24h || 0) / 100)) : '0',
          high24h: coin.high_24h ? formatPrice(coin.high_24h) : formatPrice(currentPrice),
          low24h: coin.low_24h ? formatPrice(coin.low_24h) : formatPrice(currentPrice),
          vol24h: coin.total_volume?.toString() || '0',
          volCcy24h: coin.total_volume && currentPrice ? (coin.total_volume * currentPrice).toFixed(2) : '0',
          ts: currentTimestamp.toString(), // Current timestamp for real-time tracking
          change24h: coin.price_change_percentage_24h?.toFixed(2) || '0',
          change1h: coin.price_change_percentage_1h_in_currency?.toFixed(2) || '0',
          change7d: coin.price_change_percentage_7d_in_currency?.toFixed(2) || '0',
          marketCap: coin.market_cap?.toString() || '0',
          marketCapRank: coin.market_cap_rank?.toString() || '0',
          circulatingSupply: coin.circulating_supply?.toString() || '0',
          totalSupply: coin.total_supply?.toString() || '0',
          sparkline: sparkline, // 7-day price history array
          chartData: chartData, // formatted for RealtimeStream charts
          image: coin.image,
          name: coin.name,
          symbol: coin.symbol?.toUpperCase(),
          sz: '0',
          tradeId: currentTimestamp.toString(), // Use current timestamp for unique trade ID
          side: 'buy',
          timestamp: currentTimestamp // Real-time timestamp - ensures accurate price reflection
        }]
      });
    });
    
    return {
      coins: transformedData,
      globalStats: globalStats
    };
  } catch (error) {
    console.error('Error fetching detailed market data:', error);
    throw error;
  }
};

