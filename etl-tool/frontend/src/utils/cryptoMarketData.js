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
 */
export const fetchDetailedMarketData = async () => {
  try {
    const ids = Object.values(TRACKED_CRYPTO_IDS).join(',');
    
    // Fetch coin market data and global stats in parallel using backend proxy
    const [coinsResponse, globalStatsResponse] = await Promise.all([
      fetch(
        `${API_BASE_URL}/api/crypto/markets?vs_currency=usd&ids=${ids}&order=market_cap_desc&per_page=20&page=1&sparkline=true&price_change_percentage=1h%2C24h%2C7d`
      ),
      fetch(`${API_BASE_URL}/api/crypto/global-stats`).catch(() => null) // Optional, don't fail if this fails
    ]);
    
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
    
    if (globalStatsResponse && globalStatsResponse.ok) {
      const globalData = await globalStatsResponse.json();
      globalStats = globalData.data;
    }
    
    // Transform to our format
    const transformedData = [];
    
    coinsData.forEach((coin) => {
      const symbol = ID_TO_SYMBOL[coin.id];
      if (!symbol) return;
      
      const currentPrice = coin.current_price || 0;
      const sparkline = coin.sparkline_in_7d?.price || [];
      
      // Transform sparkline into chartData points (for mini and full charts)
      const chartData = sparkline.length > 0
        ? sparkline.map((price, index) => {
            // Spread points across last 7 days
            const now = Date.now();
            const ratio = index / Math.max(sparkline.length - 1, 1);
            const timestamp = now - (1 - ratio) * 7 * 24 * 60 * 60 * 1000;
            return {
              time: new Date(timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
              price: price,
              timestamp
            };
          })
        : [];
      
      transformedData.push({
        arg: {
          channel: 'tickers',
          instId: symbol.replace('USDT', '-USDT')
        },
        data: [{
          instId: symbol.replace('USDT', '-USDT'),
          last: currentPrice.toString(),
          px: currentPrice.toString(), // Primary price field for RealtimeStream
          p: currentPrice.toString(), // Alternative price field
          lastSz: '0',
          askPx: (currentPrice * 1.001).toFixed(2),
          askSz: '0',
          bidPx: (currentPrice * 0.999).toFixed(2),
          bidSz: '0',
          open24h: currentPrice ? (currentPrice / (1 + (coin.price_change_percentage_24h || 0) / 100)).toFixed(2) : '0',
          high24h: coin.high_24h?.toString() || currentPrice.toString() || '0',
          low24h: coin.low_24h?.toString() || currentPrice.toString() || '0',
          vol24h: coin.total_volume?.toString() || '0',
          volCcy24h: (coin.total_volume * currentPrice)?.toString() || '0',
          ts: Date.now().toString(),
          change24h: coin.price_change_percentage_24h?.toString() || '0',
          change1h: coin.price_change_percentage_1h_in_currency?.toString() || '0',
          change7d: coin.price_change_percentage_7d_in_currency?.toString() || '0',
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
          tradeId: Date.now().toString(),
          side: 'buy',
          timestamp: Date.now()
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

