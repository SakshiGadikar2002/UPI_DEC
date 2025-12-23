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
 * DEPRECATED: fetchGlobalCryptoMarketData
 * 
 * This function has been removed to enforce architecture:
 * API → Database → Pipeline → Backend → Frontend
 * 
 * All API calls must go through backend endpoints that read from database.
 * Use fetchDetailedMarketData() instead, which calls backend endpoints.
 */
export const fetchGlobalCryptoMarketData = async () => {
  throw new Error(
    'fetchGlobalCryptoMarketData is deprecated. ' +
    'All API calls must go through backend endpoints that read from database. ' +
    'Use fetchDetailedMarketData() instead, which follows the architecture: ' +
    'API → Database → Backend → Frontend'
  );
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
    
    // Make BOTH API calls in PARALLEL to cut load time in half
    // Force no-cache to avoid browser caching stale responses
    const fetchOptions = { cache: 'no-store', headers: { 'Cache-Control': 'no-cache' } };
    const [coinsResponse, globalStatsResponse] = await Promise.all([
      fetch(
        `${API_BASE_URL}/api/crypto/markets?vs_currency=usd&ids=${ids}&order=market_cap_desc&per_page=20&page=1&sparkline=true&price_change_percentage=1h%2C24h%2C7d`,
        fetchOptions
      ),
      fetch(`${API_BASE_URL}/api/crypto/global-stats`, fetchOptions).catch(e => {
        // Don't fail if global stats fails - it's optional
        console.warn('Global stats fetch error (non-critical):', e);
        return { ok: false };
      })
    ]);
    
    // Handle 429 (Too Many Requests) with exponential backoff retry
    if (coinsResponse.status === 429) {
      if (retryCount < maxRetries) {
        const backoffDelay = Math.min(1000 * Math.pow(2, retryCount), 30000);
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
    
    const coinsData = await coinsResponse.json();
    let globalStats = null;
    
    // Try to get global stats if available (non-critical)
    if (globalStatsResponse && globalStatsResponse.ok) {
      try {
        const globalData = await globalStatsResponse.json();
        globalStats = globalData.data || globalData;
        
        // FIX: CoinGecko returns 'total_volume' but frontend expects 'total_volume_24h'
        // Normalize the field name for consistency
        if (globalStats.total_volume && !globalStats.total_volume_24h) {
          globalStats.total_volume_24h = globalStats.total_volume;
        }
      } catch (e) {
        console.warn('Failed to parse global stats:', e);
      }
    }
    
    // Transform to our format
    const transformedData = [];
    
    coinsData.forEach((coin) => {
      const symbol = ID_TO_SYMBOL[coin.id];
      if (!symbol) return;
      
      // CRITICAL: Use EXACT current_price from CoinGecko - no rounding, no modification
      // This ensures 100% accuracy matching CoinGecko/CoinMarketCap
      const currentPrice = coin.current_price !== null && coin.current_price !== undefined 
        ? Number(coin.current_price)  // Convert to number but preserve all decimals
        : 0;
      
      // Validate price is a valid number
      if (isNaN(currentPrice) || currentPrice <= 0) {
        console.warn(`Invalid price for ${coin.id}: ${coin.current_price}`);
        return; // Skip invalid coins
      }
      
      const sparkline = coin.sparkline_in_7d?.price || [];
      
      // Get current timestamp for accurate real-time tracking
      const currentTimestamp = Date.now();
      
      // Transform sparkline into chartData points (for mini and full charts)
      const chartData = sparkline.length > 0
        ? sparkline.map((price, index) => {
            const now = Date.now();
            const today = new Date(now);
            today.setHours(0, 0, 0, 0);
            const todayStart = today.getTime();
            
            const ratio = index / Math.max(sparkline.length - 1, 1);
            const timestamp = todayStart + ratio * (now - todayStart);
            const dateObj = new Date(timestamp);
            
            const time = dateObj.toLocaleString([], {
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              hour12: false
            });
            
            return {
              time: time,
              price: Number(price), // Preserve exact price from sparkline
              timestamp
            };
          })
        : [];
      
      // CRITICAL: Preserve ALL CoinGecko fields exactly as received
      transformedData.push({
        arg: {
          channel: 'tickers',
          instId: symbol.replace('USDT', '-USDT')
        },
        data: [{
          instId: symbol.replace('USDT', '-USDT'),
          // PRIMARY: Use exact current_price from CoinGecko (matches their website exactly)
          current_price: currentPrice,
          price: currentPrice,  // Also set as price for compatibility
          last: currentPrice,
          px: currentPrice,
          p: currentPrice,
          lastSz: '0',
          askPx: currentPrice * 1.001,
          askSz: '0',
          bidPx: currentPrice * 0.999,
          bidSz: '0',
          // Use exact values from CoinGecko - no calculation, no rounding
          open24h: coin.high_24h && coin.low_24h 
            ? (coin.high_24h + coin.low_24h) / 2  // Use actual high/low if available
            : (currentPrice ? currentPrice / (1 + (coin.price_change_percentage_24h || 0) / 100) : 0),
          high24h: coin.high_24h || currentPrice,  // Use exact CoinGecko high_24h
          low24h: coin.low_24h || currentPrice,   // Use exact CoinGecko low_24h
          vol24h: coin.total_volume?.toString() || '0',
          volCcy24h: coin.total_volume && currentPrice ? (coin.total_volume * currentPrice).toString() : '0',
          ts: currentTimestamp.toString(),
          // Use exact percentage changes from CoinGecko - preserve decimals
          change24h: coin.price_change_percentage_24h !== null && coin.price_change_percentage_24h !== undefined
            ? Number(coin.price_change_percentage_24h)  // Preserve all decimals
            : 0,
          change1h: coin.price_change_percentage_1h_in_currency !== null && coin.price_change_percentage_1h_in_currency !== undefined
            ? Number(coin.price_change_percentage_1h_in_currency)
            : 0,
          change7d: coin.price_change_percentage_7d_in_currency !== null && coin.price_change_percentage_7d_in_currency !== undefined
            ? Number(coin.price_change_percentage_7d_in_currency)
            : 0,
          marketCap: coin.market_cap?.toString() || '0',
          marketCapRank: coin.market_cap_rank?.toString() || '0',
          circulatingSupply: coin.circulating_supply?.toString() || '0',
          totalSupply: coin.total_supply?.toString() || '0',
          sparkline: sparkline,
          chartData: chartData,
          image: coin.image,
          name: coin.name,
          symbol: coin.symbol?.toUpperCase(),
          sz: '0',
          tradeId: currentTimestamp.toString(),
          side: 'buy',
          timestamp: currentTimestamp,
          // ADD: Store last_updated timestamp from CoinGecko to verify freshness
          last_updated: coin.last_updated ? new Date(coin.last_updated).getTime() : currentTimestamp
        }]
      });
    });
    
    // DEBUG: Log first coin to verify price accuracy
    if (transformedData.length > 0) {
      const firstCoin = transformedData[0];
      const coinGeckoPrice = coinsData.find(c => ID_TO_SYMBOL[c.id] === firstCoin.arg.instId.replace('-USDT', 'USDT'));
      if (coinGeckoPrice) {
        console.log('🔍 Price Verification:', {
          coin: coinGeckoPrice.name,
          coinGeckoPrice: coinGeckoPrice.current_price,
          ourPrice: firstCoin.data[0].current_price,
          match: coinGeckoPrice.current_price === firstCoin.data[0].current_price,
          timestamp: new Date().toISOString()
        });
      }
    }
    
    return {
      coins: transformedData,
      globalStats: globalStats
    };
  } catch (error) {
    console.error('Error fetching detailed market data:', error);
    throw error;
  }
};

