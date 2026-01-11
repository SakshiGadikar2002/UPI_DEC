import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import io from 'socket.io-client';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
  ReferenceLine,
  Brush,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import './RealtimeStream.css';
import { OKX_CONFIG, BINANCE_CONFIG } from '../utils/websocketConfig';

// Use relative URLs - works when frontend is served from same port as backend
const API_BASE_URL = '';
const SOCKET_URL = window.location.origin; // For socket.io, use current origin

// Get instruments from config based on exchange - normalize to symbol format (BTCUSDT)
const getInstrumentsFromConfig = (exchange) => {
  const allInstruments = [];
  
  if (exchange === 'okx') {
    // Get OKX instruments and convert to symbol format
    Object.values(OKX_CONFIG.INSTRUMENTS).forEach(inst => {
      if (inst !== 'ALL') {
        // Convert BTC-USDT to BTCUSDT format
        const symbol = inst.replace('-', '');
        if (!allInstruments.includes(symbol)) {
          allInstruments.push(symbol);
        }
      }
    });
  } else if (exchange === 'binance') {
    // Get Binance symbols
    Object.values(BINANCE_CONFIG.SYMBOLS).forEach(symbol => {
      if (symbol !== 'ALL') {
        const upperSymbol = symbol.toUpperCase();
        if (!allInstruments.includes(upperSymbol)) {
          allInstruments.push(upperSymbol);
        }
      }
    });
  } else if (exchange === 'global') {
    // For global exchange, return all tracked crypto symbols
    return TRACKED_CRYPTO_SYMBOLS;
  }
  // For 'custom', return empty array - will use instruments from subscription data
  
  return allInstruments.sort();
};

// Crypto name mapping - proper names with symbols (top 20 most liquid real-time assets)
const CRYPTO_NAMES = {
  "BTCUSDT": { name: "Bitcoin", symbol: "BTC" },
  "ETHUSDT": { name: "Ethereum", symbol: "ETH" },
  "BNBUSDT": { name: "BNB", symbol: "BNB" },
  "SOLUSDT": { name: "Solana", symbol: "SOL" },
  "XRPUSDT": { name: "XRP", symbol: "XRP" },
  "ADAUSDT": { name: "Cardano", symbol: "ADA" },
  "DOGEUSDT": { name: "Dogecoin", symbol: "DOGE" },
  "MATICUSDT": { name: "Polygon", symbol: "MATIC" },
  "DOTUSDT": { name: "Polkadot", symbol: "DOT" },
  "AVAXUSDT": { name: "Avalanche", symbol: "AVAX" },
  "SHIBUSDT": { name: "Shiba Inu", symbol: "SHIB" },
  "TRXUSDT": { name: "TRON", symbol: "TRX" },
  "LINKUSDT": { name: "Chainlink", symbol: "LINK" },
  "UNIUSDT": { name: "Uniswap", symbol: "UNI" },
  "ATOMUSDT": { name: "Cosmos", symbol: "ATOM" },
  "LTCUSDT": { name: "Litecoin", symbol: "LTC" },
  "ETCUSDT": { name: "Ethereum Classic", symbol: "ETC" },
  "XLMUSDT": { name: "Stellar", symbol: "XLM" },
  "ALGOUSDT": { name: "Algorand", symbol: "ALGO" },
  "NEARUSDT": { name: "NEAR Protocol", symbol: "NEAR" }
};

// List of top 20 tracked crypto symbols (most liquid real-time assets)
const TRACKED_CRYPTO_SYMBOLS = [
  "BTCUSDT",
  "ETHUSDT",
  "BNBUSDT",
  "SOLUSDT",
  "XRPUSDT",
  "ADAUSDT",
  "DOGEUSDT",
  "MATICUSDT",
  "DOTUSDT",
  "AVAXUSDT",
  "SHIBUSDT",
  "TRXUSDT",
  "LINKUSDT",
  "UNIUSDT",
  "ATOMUSDT",
  "LTCUSDT",
  "ETCUSDT",
  "XLMUSDT",
  "ALGOUSDT",
  "NEARUSDT"
];

// Get crypto icon configuration (colors and logo)
const getCryptoIconConfig = (symbol) => {
  const cryptoConfig = {
    'BTC': { 
      bg: 'linear-gradient(135deg, #f7931a 0%, #f7931a 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/1/small/bitcoin.png'
    },
    'ETH': { 
      bg: 'linear-gradient(135deg, #627eea 0%, #627eea 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/279/small/ethereum.png'
    },
    'BNB': { 
      bg: 'linear-gradient(135deg, #f3ba2f 0%, #f3ba2f 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/825/small/bnb-icon2_2x.png'
    },
    'XRP': { 
      bg: 'linear-gradient(135deg, #000000 0%, #23292f 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/44/small/xrp-symbol-white-128.png'
    },
    'ADA': { 
      bg: 'linear-gradient(135deg, #0033ad 0%, #0033ad 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/975/small/cardano.png'
    },
    'SOL': { 
      bg: 'linear-gradient(135deg, #9945ff 0%, #14f195 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/4128/small/solana.png'
    },
    'DOGE': { 
      bg: 'linear-gradient(135deg, #c2a633 0%, #c2a633 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/5/small/dogecoin.png'
    },
    'MATIC': { 
      bg: 'linear-gradient(135deg, #8247e5 0%, #8247e5 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/4713/small/matic-token-icon.png'
    },
    'DOT': { 
      bg: 'linear-gradient(135deg, #e6007a 0%, #e6007a 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/12171/small/polkadot.png'
    },
    'LTC': { 
      bg: 'linear-gradient(135deg, #345d9d 0%, #345d9d 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/2/small/litecoin.png'
    },
    'AVAX': { 
      bg: 'linear-gradient(135deg, #e84142 0%, #e84142 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/12559/small/avalanche-avax-logo.png'
    },
    'SHIB': { 
      bg: 'linear-gradient(135deg, #ffa409 0%, #ffa409 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/11939/small/shiba.png'
    },
    'ATOM': { 
      bg: 'linear-gradient(135deg, #2e3148 0%, #2e3148 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/1481/small/cosmos_hub.png'
    },
    'TRX': { 
      bg: 'linear-gradient(135deg, #ef0027 0%, #ef0027 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/1094/small/tron-logo.png'
    },
    'ETC': { 
      bg: 'linear-gradient(135deg, #328332 0%, #328332 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/453/small/ethereum-classic-logo.png'
    },
    'LINK': { 
      bg: 'linear-gradient(135deg, #2e5bb3 0%, #2e5bb3 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/877/small/chainlink-new-logo.png'
    },
    'UNI': { 
      bg: 'linear-gradient(135deg, #ff007a 0%, #ff007a 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/12504/small/uniswap-uni.png'
    },
    'ALGO': { 
      bg: 'linear-gradient(135deg, #000000 0%, #000000 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/4380/small/download.png'
    },
    'VET': { 
      bg: 'linear-gradient(135deg, #15bdff 0%, #15bdff 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/1167/small/vechain.png'
    },
    'ICP': { 
      bg: 'linear-gradient(135deg, #f15e22 0%, #f15e22 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/14495/small/Internet_Computer_logo.png'
    },
    'THETA': { 
      bg: 'linear-gradient(135deg, #2ab8e6 0%, #2ab8e6 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/2538/small/theta-token-logo.png'
    },
    'AXS': { 
      bg: 'linear-gradient(135deg, #0055d5 0%, #0055d5 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/13029/small/axie_infinity_logo.png'
    },
    'SAND': { 
      bg: 'linear-gradient(135deg, #00adef 0%, #00adef 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/12129/small/sandbox_logo.png'
    },
    'EOS': { 
      bg: 'linear-gradient(135deg, #000000 0%, #000000 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/738/small/eos-eos-logo.png'
    },
    'AAVE': { 
      bg: 'linear-gradient(135deg, #b6509e 0%, #b6509e 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/12645/small/AAVE.png'
    },
    'NEAR': { 
      bg: 'linear-gradient(135deg, #000000 0%, #000000 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/10365/small/near.png'
    },
    'FIL': { 
      bg: 'linear-gradient(135deg, #0090ff 0%, #0090ff 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/12817/small/filecoin.png'
    },
    'XLM': { 
      bg: 'linear-gradient(135deg, #7d00ff 0%, #7d00ff 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/100/small/stellar.png'
    },
    'XTZ': { 
      bg: 'linear-gradient(135deg, #2c7df7 0%, #2c7df7 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/976/small/tezos.png'
    },
    'USDC': { 
      bg: 'linear-gradient(135deg, #2775ca 0%, #2775ca 100%)', 
      text: '#fff',
      logo: 'https://assets.coingecko.com/coins/images/6319/small/USD_Coin_icon.png'
    },
  };
  return cryptoConfig[symbol] || { 
    bg: 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)', 
    text: '#fff',
    logo: null
  };
};

// Convert symbol to OKX format (BTCUSDT -> BTC-USDT)
const convertToOKXFormat = (symbol) => {
  if (symbol.endsWith('USDT')) {
    return symbol.replace('USDT', '-USDT');
  }
  return symbol;
};

// Helper function to format price with appropriate decimal places
const formatPrice = (price) => {
  if (!price || price <= 0) return 'N/A';
  
  // For prices >= $1, show 2 decimals
  // For prices < $1, show up to 6 decimals (for coins like SHIB, DOGE)
  if (price >= 1) {
    return price.toLocaleString('en-US', { 
      minimumFractionDigits: 2, 
      maximumFractionDigits: 2 
    });
  } else {
    // For small prices, show significant digits
    const decimals = Math.max(2, 6 - Math.floor(Math.log10(price)));
    return price.toLocaleString('en-US', { 
      minimumFractionDigits: decimals, 
      maximumFractionDigits: decimals 
    });
  }
};

 function RealtimeStream({ onDataCollected, websocketData, messages, latencyData, throughputData, defaultTab = 'dashboard', exchange = 'okx', showTopMovers = true }) {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionId, setConnectionId] = useState(null);
  const [streamData, setStreamData] = useState([]);
  const [stats, setStats] = useState({
    totalMessages: 0,
    messagesPerSecond: 0,
    lastUpdate: null
  });
  // Use exchange from props (passed from WebSocketSection)
  const [channel, setChannel] = useState('trades'); // Default to 'trades' which works
  const [instId, setInstId] = useState('BTC-USDT');
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [streamType, setStreamType] = useState('trade');
  
  // Sync instId when symbol changes (for OKX)
  useEffect(() => {
    if (exchange === 'okx') {
      // When OKX is selected, update instId based on symbol
      const okxFormat = convertToOKXFormat(symbol);
      if (okxFormat !== instId) {
        setInstId(okxFormat);
      }
    }
  }, [symbol, exchange]); // eslint-disable-line react-hooks/exhaustive-deps
  
  // Sync symbol when instId changes (for OKX)
  useEffect(() => {
    if (exchange === 'okx' && instId) {
      // Convert OKX format back to symbol format (BTC-USDT -> BTCUSDT)
      const symbolFormat = instId.replace('-', '');
      if (TRACKED_CRYPTO_SYMBOLS.includes(symbolFormat) && symbolFormat !== symbol) {
        setSymbol(symbolFormat);
      }
    }
  }, [instId, exchange]); // eslint-disable-line react-hooks/exhaustive-deps
  
  // When exchange changes, sync the symbol/instId
  const handleExchangeChange = (newExchange) => {
    // Note: Exchange is controlled by parent component (WebSocketSection)
    // This handler is kept for compatibility but exchange should be changed in parent
    if (newExchange === 'okx') {
      // Convert current symbol to OKX format
      setInstId(convertToOKXFormat(symbol));
    }
  };
  const [customWebsocketUrl, setCustomWebsocketUrl] = useState('');
  const [subscribeMessage, setSubscribeMessage] = useState('');
  const [chartData, setChartData] = useState([]);
  const [showCharts, setShowCharts] = useState(true);
  const [viewMode, setViewMode] = useState('charts'); // 'charts' or 'raw'
  const [activeTab, setActiveTab] = useState(defaultTab); // 'live', 'list', 'compare', or 'dashboard'
  const [historyData, setHistoryData] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedInstruments, setSelectedInstruments] = useState(['BTCUSDT', 'ETHUSDT', 'BNBUSDT']); // Default selected instruments
  const [comparisonData, setComparisonData] = useState([]);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [initialPrices, setInitialPrices] = useState({}); // Store initial prices for percentage calculation
  const [timeFilter, setTimeFilter] = useState('24h'); // Time filter: '1h', '6h', '24h'
  const [allComparisonData, setAllComparisonData] = useState([]); // Store all data for filtering
  const [isInstrumentSelectorCollapsed, setIsInstrumentSelectorCollapsed] = useState(false); // Collapsible state
  
// Forward-fill missing comparison values so every timestamp has every symbol
const fillComparisonData = (dataPoints, symbols) => {
  const lastValues = {};
  const lastPrices = {};
  return dataPoints.map((point) => {
    const filled = { ...point };
    symbols.forEach((sym) => {
      if (typeof filled[sym] === 'number') {
        lastValues[sym] = filled[sym];
      } else if (lastValues[sym] !== undefined) {
        filled[sym] = lastValues[sym];
      }

      const priceKey = `${sym}_price`;
      if (typeof filled[priceKey] === 'number') {
        lastPrices[sym] = filled[priceKey];
      } else if (lastPrices[sym] !== undefined) {
        filled[priceKey] = lastPrices[sym];
      }
    });
    return filled;
  });
};

  const socketRef = useRef(null);
  const priceSocketRef = useRef(null); // Separate socket for price updates
  const historySaveIntervalRef = useRef(null);
  const historyRefreshIntervalRef = useRef(null);
  const latencyUpdateIntervalRef = useRef(null);
  const lastPriceRef = useRef(null);
  const messageCountRef = useRef(0);
  const lastSecondRef = useRef(Date.now());
  const lastDataTimestampRef = useRef(Date.now());
  const maxDisplayItems = 100; // Show last 100 messages
  const maxChartPoints = 200; // Keep last 200 points for charts
  const statsIntervalRef = useRef(null);
  const currentConnectionIdRef = useRef(null);

  // Chart data cache to avoid refetching on every refresh
  const chartDataCacheRef = useRef({});
  
  // Update prices from SocketIO in real-time (no loading, no blinking)
  const updatePricesFromSocket = React.useCallback((priceUpdates) => {
    setHistoryData(prevData => {
      if (prevData.length === 0) {
        // If no data, convert updates to full format
        return priceUpdates.map(update => {
          const updateTimestamp = update.timestamp || update.last_update || Date.now();
          const latency = Math.max(0, Date.now() - updateTimestamp);
          return {
            symbol: update.symbol,
            name: update.name || update.symbol,
            price: update.current_price !== undefined && update.current_price !== null ? update.current_price : 0,
            change1h: update.change1h !== undefined && update.change1h !== null ? update.change1h : 0,
            change6h: update.change6h !== undefined && update.change6h !== null ? update.change6h : 0,
            change12h: update.change12h !== undefined && update.change12h !== null ? update.change12h : 0,
            latency: latency,
            lastUpdateTimestamp: updateTimestamp,
            chartData: chartDataCacheRef.current[update.symbol] || []
          };
        });
      }
      
      // Create map of updates for quick lookup
      const updatesMap = new Map(priceUpdates.map(update => [update.symbol, update]));
      
      // Check if we need to fetch chart data for any symbols
      const symbolsNeedingChartData = [];
      prevData.forEach(item => {
        const update = updatesMap.get(item.symbol);
        if (update && (!item.chartData || item.chartData.length <= 1) && !chartDataCacheRef.current[item.symbol]) {
          symbolsNeedingChartData.push(item.symbol);
        }
      });
      
      // Fetch chart data for symbols that need it (async, won't block update)
      if (symbolsNeedingChartData.length > 0) {
        symbolsNeedingChartData.forEach(async (symbol) => {
          try {
            const historyResponse = await fetch(
              `${API_BASE_URL}/api/realtime-history/get?symbol=${symbol}&hours=12`
            );
            const historyResult = await historyResponse.json();
            
            if (historyResult.snapshots && historyResult.snapshots.length > 0) {
              const chartData = [];
              const currentTime = Date.now();
              const twelveHoursAgo = currentTime - (12 * 60 * 60 * 1000);
              const filteredSnapshots = historyResult.snapshots.filter(
                s => s.timestamp >= twelveHoursAgo
              );
              
              const sampleInterval = 10 * 60 * 1000;
              let lastSampledTime = 0;
              
              filteredSnapshots.forEach(snapshot => {
                if (snapshot.timestamp - lastSampledTime >= sampleInterval || chartData.length === 0) {
                  chartData.push({
                    time: new Date(snapshot.timestamp).toLocaleTimeString(),
                    price: snapshot.price,
                    timestamp: snapshot.timestamp
                  });
                  lastSampledTime = snapshot.timestamp;
                }
              });
              
              if (chartData.length > 1) {
                chartDataCacheRef.current[symbol] = chartData;
                // Update the item with chart data
                setHistoryData(prev => prev.map(item => 
                  item.symbol === symbol 
                    ? { ...item, chartData: chartData }
                    : item
                ));
              }
            }
          } catch (error) {
            console.error(`Error loading chart data for ${symbol}:`, error);
          }
        });
      }
      
      // Create a set of existing symbols for quick lookup
      const existingSymbols = new Set(prevData.map(item => item.symbol));
      
      // Update only changed values smoothly
      const updatedData = prevData.map(item => {
        const update = updatesMap.get(item.symbol);
        if (update) {
          // Calculate latency from timestamp (if provided) or use current time
          const updateTimestamp = update.timestamp || update.last_update || Date.now();
          const latency = Math.max(0, Date.now() - updateTimestamp);
          
          // Get update values (handle 0 properly)
          const newPrice = update.current_price !== undefined && update.current_price !== null ? update.current_price : item.price;
          const newChange1h = update.change1h !== undefined && update.change1h !== null ? update.change1h : item.change1h;
          const newChange6h = update.change6h !== undefined && update.change6h !== null ? update.change6h : item.change6h;
          const newChange12h = update.change12h !== undefined && update.change12h !== null ? update.change12h : item.change12h;
          
          // Only update if values actually changed
          const priceChanged = Math.abs(item.price - newPrice) > 0.01;
          const change1hChanged = Math.abs((item.change1h || 0) - newChange1h) > 0.01;
          const change6hChanged = Math.abs((item.change6h || 0) - newChange6h) > 0.01;
          const change12hChanged = Math.abs((item.change12h || 0) - newChange12h) > 0.01;
          const latencyChanged = Math.abs((item.latency || 0) - latency) > 100; // Update if latency changed by more than 100ms
          
          if (priceChanged || change1hChanged || change6hChanged || change12hChanged || latencyChanged) {
            // Update chart data with latest price point
            let updatedChartData = item.chartData || chartDataCacheRef.current[item.symbol] || [];
            
            // If we have a new price, add it to chart data (keep last 50 points)
            if (newPrice > 0) {
              const newPoint = {
                time: new Date(updateTimestamp).toLocaleTimeString(),
                price: newPrice,
                timestamp: updateTimestamp
              };
              
              // Add new point and keep only last 50 points
              updatedChartData = [...updatedChartData, newPoint].slice(-50);
              
              // Update cache
              chartDataCacheRef.current[item.symbol] = updatedChartData;
            }
            
            return {
              ...item,
              price: newPrice,
              change1h: newChange1h,
              change6h: newChange6h,
              change12h: newChange12h,
              latency: latency,
              lastUpdateTimestamp: updateTimestamp,
              chartData: updatedChartData
            };
          }
        }
        // Return unchanged item to prevent re-render
        return item;
      });
      
      // Add any new symbols that don't exist in prevData
      const newItems = priceUpdates
        .filter(update => !existingSymbols.has(update.symbol))
        .map(update => {
          const updateTimestamp = update.timestamp || update.last_update || Date.now();
          const latency = Math.max(0, Date.now() - updateTimestamp);
          return {
            symbol: update.symbol,
            name: update.name || update.symbol,
            price: update.current_price !== undefined && update.current_price !== null ? update.current_price : 0,
            change1h: update.change1h !== undefined && update.change1h !== null ? update.change1h : 0,
            change6h: update.change6h !== undefined && update.change6h !== null ? update.change6h : 0,
            change12h: update.change12h !== undefined && update.change12h !== null ? update.change12h : 0,
            latency: latency,
            lastUpdateTimestamp: updateTimestamp,
            chartData: chartDataCacheRef.current[update.symbol] || []
          };
        });
      
      return [...updatedData, ...newItems];
    });
  }, []);
  
  // Process real-time data from WebSocketSection props - runs continuously for dashboard and list tabs
  useEffect(() => {
    // Always process if we have websocketData or messages (for real-time updates in dashboard/list)
    if (!websocketData && (!messages || messages.length === 0)) return;
    
    // Debug logging for global exchange
    if (exchange === 'global' && websocketData?.data) {
      console.log('🌍 Processing global crypto data:', {
        dataLength: Array.isArray(websocketData.data) ? websocketData.data.length : 'not array',
        hasGlobalStats: !!websocketData.globalStats,
        exchange: exchange
      });
    }

    // Extract instrument symbol helper - convert to BTCUSDT format
    const getInstrumentSymbol = (data) => {
      if (!data) return null;
      let symbol = null;
      
      if (data.arg && data.arg.instId) {
        symbol = data.arg.instId; // OKX format: BTC-USDT
      } else if (data.stream) {
        symbol = data.stream.split('@')[0].toUpperCase(); // Binance: btcusdt@trade
      } else if (data.s) {
        symbol = data.s.toUpperCase(); // Binance direct: BTCUSDT
      } else if (Array.isArray(data) && data.length > 0 && data[0].instId) {
        symbol = data[0].instId;
      }
      
      // Convert to BTCUSDT format (remove dash if present)
      if (symbol) {
        return symbol.replace('-', '').toUpperCase();
      }
      return null;
    };

    // Extract price helper - prefer CoinGecko's raw current_price so values match exactly
    const getPrice = (data, depth = 0, maxDepth = 5) => {
      if (!data || depth > maxDepth) return null;
      if (typeof data === 'object' && data !== null) {
        const priceFields = ['current_price', 'price', 'px', 'p', 'last', 'c', 'close', 'lastPrice', 'tradePrice'];
        for (const field of priceFields) {
          if (data[field] !== undefined && data[field] !== null) {
            const priceVal = data[field];
            if (typeof priceVal === 'string') {
              const parsed = parseFloat(priceVal.trim());
              if (!isNaN(parsed)) return parsed;
            } else if (typeof priceVal === 'number' && !isNaN(priceVal)) {
              return priceVal;
            }
          }
        }
        if (Array.isArray(data) && data.length > 0) {
          const nestedPrice = getPrice(data[0], depth + 1, maxDepth);
          if (nestedPrice !== null) return nestedPrice;
        } else if (data.data) {
          const nestedPrice = getPrice(data.data, depth + 1, maxDepth);
          if (nestedPrice !== null) return nestedPrice;
        }
      }
      return null;
    };

    // Process messages to extract real-time data
    const dataMessages = messages.filter(m => m && m.type === 'data');
    const instrumentsMap = new Map();
    const chartPointsBySymbol = new Map(); // Track chart points per symbol

    // Process websocketData.data
    if (websocketData.data) {
      const processDataItem = (item) => {
        if (item.arg && Array.isArray(item.data)) {
          item.data.forEach(trade => {
            const symbol = getInstrumentSymbol({ ...trade, arg: item.arg });
            const price = getPrice(trade);
            if (symbol && price) {
              const timestamp = trade.timestamp || Date.now();
              
              // Extract change percentages from CoinGecko data
              const change24h = trade.change24h ? parseFloat(trade.change24h) : 0;
              const change1h = trade.change1h ? parseFloat(trade.change1h) : 0;
              const change7d = trade.change7d ? parseFloat(trade.change7d) : 0;
              
              // Extract chartData from sparkline if available (CoinGecko format)
              let existingChartData = [];
              if (trade.chartData && Array.isArray(trade.chartData) && trade.chartData.length > 0) {
                existingChartData = trade.chartData;
              } else if (trade.sparkline && Array.isArray(trade.sparkline) && trade.sparkline.length > 0) {
                // Transform sparkline array to chartData format with current real-time timestamps
                const now = Date.now();
                const today = new Date(now);
                today.setHours(0, 0, 0, 0);
                const todayStart = today.getTime();
                
                existingChartData = trade.sparkline.map((sparkPrice, index) => {
                  // Spread points across TODAY (last 24 hours) for real-time view
                  const ratio = index / Math.max(trade.sparkline.length - 1, 1);
                  const sparkTimestamp = todayStart + ratio * (now - todayStart);
                  const dateObj = new Date(sparkTimestamp);
                  
                  // Format as date time in local timezone
                  const time = dateObj.toLocaleString([], {
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                  });
                  
                  return {
                    time: time,
                    price: sparkPrice,
                    timestamp: sparkTimestamp
                  };
                });
              }
              
              const chartPoint = {
                time: new Date(timestamp).toLocaleTimeString(),
                price,
                timestamp
              };
              
              if (!instrumentsMap.has(symbol)) {
                instrumentsMap.set(symbol, {
                  symbol,
                  name: trade.name || CRYPTO_NAMES[symbol.replace('-', '')]?.name || symbol,
                  price,
                  change1h: change1h,
                  change6h: 0, // Not available from CoinGecko
                  change12h: 0, // Not available from CoinGecko
                  change24h: change24h,
                  change7d: change7d,
                  marketCap: trade.marketCap ? parseFloat(trade.marketCap) : 0,
                  volume24h: trade.vol24h ? parseFloat(trade.vol24h) : 0,
                  latency: latencyData && latencyData.length > 0 ? latencyData[latencyData.length - 1]?.latency || 0 : 0,
                  lastUpdateTimestamp: timestamp,
                  chartData: existingChartData.length > 0 ? existingChartData : []
                });
                chartPointsBySymbol.set(symbol, existingChartData.length > 0 ? existingChartData : [chartPoint]);
              } else {
                const existing = instrumentsMap.get(symbol);
                // Merge chartData - use existing if it has more points, otherwise use new
                const mergedChartData = existingChartData.length > (existing.chartData?.length || 0) 
                  ? existingChartData 
                  : (existing.chartData || []);
                
                instrumentsMap.set(symbol, {
                  ...existing,
                  price,
                  change1h: change1h || existing.change1h,
                  change24h: change24h || existing.change24h,
                  change7d: change7d || existing.change7d,
                  marketCap: trade.marketCap ? parseFloat(trade.marketCap) : existing.marketCap,
                  volume24h: trade.vol24h ? parseFloat(trade.vol24h) : existing.volume24h,
                  lastUpdateTimestamp: timestamp,
                  chartData: mergedChartData
                });
                const existingPoints = chartPointsBySymbol.get(symbol) || [];
                chartPointsBySymbol.set(symbol, mergedChartData.length > 0 ? mergedChartData : [...existingPoints, chartPoint].slice(-50));
              }
            }
          });
        } else if (item.stream && item.data) {
          const symbol = getInstrumentSymbol(item);
          const price = getPrice(item.data);
          if (symbol && price) {
            const timestamp = Date.now();
            const chartPoint = {
              time: new Date(timestamp).toLocaleTimeString(),
              price,
              timestamp
            };
            
            if (!instrumentsMap.has(symbol)) {
              instrumentsMap.set(symbol, {
                symbol,
                name: CRYPTO_NAMES[symbol.replace('-', '')]?.name || symbol,
                price,
                change1h: 0,
                change6h: 0,
                change12h: 0,
                latency: latencyData && latencyData.length > 0 ? latencyData[latencyData.length - 1]?.latency || 0 : 0,
                lastUpdateTimestamp: timestamp,
                chartData: []
              });
              chartPointsBySymbol.set(symbol, [chartPoint]);
            } else {
              const existing = instrumentsMap.get(symbol);
              instrumentsMap.set(symbol, {
                ...existing,
                price,
                lastUpdateTimestamp: timestamp
              });
              const existingPoints = chartPointsBySymbol.get(symbol) || [];
              chartPointsBySymbol.set(symbol, [...existingPoints, chartPoint].slice(-50));
            }
          }
        }
      };

      if (Array.isArray(websocketData.data)) {
        websocketData.data.forEach((item, idx) => {
          if (exchange === 'global' && idx === 0) {
            console.log('🌍 Processing first data item:', item);
          }
          processDataItem(item);
        });
      } else {
        if (exchange === 'global') {
          console.log('🌍 Processing single data item:', websocketData.data);
        }
        processDataItem(websocketData.data);
      }
    }

    // Process data messages - process all recent messages for real-time updates
    if (dataMessages && dataMessages.length > 0) {
      dataMessages.slice(-100).forEach(message => { // Process last 100 messages for better real-time updates
        if (message.data) {
          const symbol = getInstrumentSymbol(message.data);
          const price = getPrice(message.data);
          if (symbol && price) {
            const timestamp = message.timestamp?.getTime() || Date.now();
            const chartPoint = {
              time: new Date(timestamp).toLocaleTimeString(),
              price,
              timestamp
            };
            
            if (!instrumentsMap.has(symbol)) {
              instrumentsMap.set(symbol, {
                symbol,
                name: CRYPTO_NAMES[symbol]?.name || symbol,
                price,
                change1h: 0,
                change6h: 0,
                change12h: 0,
                latency: latencyData && latencyData.length > 0 ? latencyData[latencyData.length - 1]?.latency || 0 : 0,
                lastUpdateTimestamp: timestamp,
                chartData: []
              });
              chartPointsBySymbol.set(symbol, [chartPoint]);
            } else {
              const existing = instrumentsMap.get(symbol);
              instrumentsMap.set(symbol, {
                ...existing,
                price,
                lastUpdateTimestamp: timestamp
              });
              const existingPoints = chartPointsBySymbol.get(symbol) || [];
              chartPointsBySymbol.set(symbol, [...existingPoints, chartPoint].slice(-50));
            }
          }
        }
      });
    }

    // Update historyData for list view and dashboard - ensure ALL instruments from config are included
    setHistoryData(prevData => {
      const newData = Array.from(instrumentsMap.values());
      // Merge with existing data, updating prices and chart data
      const merged = new Map();
      
      // First, initialize with instruments from config based on selected exchange (even without data)
      const allConfigInstruments = getInstrumentsFromConfig(exchange);
      
      // Debug logging for global exchange
      if (exchange === 'global') {
        console.log('🌍 Initializing historyData:', {
          configInstruments: allConfigInstruments.length,
          newDataItems: newData.length,
          symbols: newData.map(d => d.symbol)
        });
      }
      
      allConfigInstruments.forEach(symbol => {
        const cryptoInfo = CRYPTO_NAMES[symbol] || { name: symbol.replace('USDT', ''), symbol: symbol.replace('USDT', '') };
        merged.set(symbol, {
          symbol,
          name: cryptoInfo.name || symbol,
          price: 0,
          change1h: 0,
          change6h: 0,
          change12h: 0,
          change24h: 0,
          latency: 0,
          lastUpdateTimestamp: null,
          chartData: [],
          hasData: false
        });
      });
      
      // For custom or global exchange, also include instruments from subscription data
      if (exchange === 'custom' || exchange === 'global') {
        newData.forEach(item => {
          if (item.symbol && !merged.has(item.symbol)) {
            const cryptoInfo = CRYPTO_NAMES[item.symbol] || { name: item.symbol.replace('USDT', ''), symbol: item.symbol.replace('USDT', '') };
            merged.set(item.symbol, {
              symbol: item.symbol,
              name: cryptoInfo.name || item.symbol,
              price: 0,
              change1h: 0,
              change6h: 0,
              change12h: 0,
              latency: 0,
              lastUpdateTimestamp: null,
              chartData: [],
              hasData: false
            });
          }
        });
      }
      
      // Then, merge with existing data (filter by exchange for OKX/Binance)
      prevData.forEach(item => {
        // For OKX/Binance, only include instruments from their config
        // For global/custom, include all instruments
        if (exchange !== 'custom' && exchange !== 'global') {
          const configInstruments = getInstrumentsFromConfig(exchange);
          if (!configInstruments.includes(item.symbol)) {
            return; // Skip instruments not in the selected exchange config
          }
        }
        
        if (!merged.has(item.symbol)) {
          merged.set(item.symbol, item);
        } else {
          merged.set(item.symbol, { ...merged.get(item.symbol), ...item });
        }
      });
      
      // Finally, update with new real-time data (filter by exchange)
      newData.forEach(item => {
        // For OKX/Binance, only process instruments from their config
        // For global/custom, process all instruments
        if (exchange !== 'custom' && exchange !== 'global') {
          const configInstruments = getInstrumentsFromConfig(exchange);
          if (!configInstruments.includes(item.symbol)) {
            return; // Skip instruments not in the selected exchange config
          }
        }
        
        const existing = merged.get(item.symbol);
        const symbolChartPoints = chartPointsBySymbol.get(item.symbol) || [];
        
        if (existing) {
          // Update existing with new price and merge chart data
          const existingChartData = existing.chartData || [];
          // Use chartData from item if available (CoinGecko sparkline), otherwise merge with symbolChartPoints
          const itemChartData = item.chartData && item.chartData.length > 0 ? item.chartData : symbolChartPoints;
          
          // Merge chart points, avoiding duplicates - prefer itemChartData if it has more points
          const allPoints = itemChartData.length > existingChartData.length 
            ? itemChartData 
            : [...existingChartData, ...symbolChartPoints]
                .filter((point, index, self) => 
                  index === self.findIndex(p => p.timestamp === point.timestamp)
                )
                .sort((a, b) => a.timestamp - b.timestamp)
                .slice(-200); // Keep more points for better charts
          
          merged.set(item.symbol, {
            ...existing,
            ...item, // Include all fields from item (change24h, change1h, marketCap, etc.)
            price: item.price,
            lastUpdateTimestamp: item.lastUpdateTimestamp,
            latency: item.latency,
            chartData: allPoints.length > 0 ? allPoints : existingChartData,
            hasData: true
          });
        } else {
          // New instrument - initialize with chart data
          const initialChartData = (item.chartData && item.chartData.length > 0) 
            ? item.chartData 
            : symbolChartPoints
                .sort((a, b) => a.timestamp - b.timestamp)
                .slice(-200); // Keep more points for better real-time charts
          merged.set(item.symbol, {
            ...item,
            chartData: initialChartData,
            hasData: true
          });
        }
      });
      
      // Sort: instruments with data first, then alphabetically
      const sortedData = Array.from(merged.values()).sort((a, b) => {
        if (a.hasData && !b.hasData) return -1;
        if (!a.hasData && b.hasData) return 1;
        return a.symbol.localeCompare(b.symbol);
      });
      
      // Debug logging for global exchange
      if (exchange === 'global') {
        console.log('🌍 Final historyData:', {
          totalItems: sortedData.length,
          itemsWithData: sortedData.filter(d => d.hasData).length,
          symbols: sortedData.map(d => d.symbol)
        });
      }
      
      return sortedData;
    });

    // Update chartData for live view graphs (aggregate all prices)
    const allChartPoints = Array.from(chartPointsBySymbol.values()).flat();
    if (allChartPoints.length > 0) {
      setChartData(prev => {
        const merged = [...prev, ...allChartPoints]
          .filter((point, index, self) => 
            index === self.findIndex(p => p.timestamp === point.timestamp && p.price === point.price)
          )
          .sort((a, b) => a.timestamp - b.timestamp)
          .slice(-maxChartPoints);
        return merged;
      });
    }

    // Update connection status - check if we have any data
    const hasData = dataMessages.length > 0 || (websocketData && websocketData.data && (Array.isArray(websocketData.data) ? websocketData.data.length > 0 : true));
    setIsConnected(hasData);

    // Update stats
    setStats(prev => ({
      ...prev,
      totalMessages: dataMessages.length,
      messagesPerSecond: throughputData && throughputData.length > 0 ? throughputData[throughputData.length - 1]?.throughput || 0 : 0,
      lastUpdate: new Date().toLocaleTimeString()
    }));
  }, [websocketData, messages, latencyData, throughputData, exchange]);

  // Set up SocketIO connection for real-time price updates
  useEffect(() => {
    // For OKX/Binance/custom streams, if data is already coming via props,
    // we don't need an extra SocketIO connection.
    // But for the global visualization view (exchange === 'global'),
    // we still want SocketIO so prices can update every few seconds
    // without requiring a full page refresh.
    if ((websocketData || messages) && exchange !== 'global') {
      return;
    }

    // Connect to SocketIO for real-time price updates
    const priceSocket = io(SOCKET_URL, {
      transports: ['polling', 'websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5,
      timeout: 20000
    });

    priceSocket.on('connect', () => {
      console.log('SocketIO connected for real-time price updates');
    });

    priceSocket.on('crypto_price_updates', (data) => {
      // Update prices in real-time automatically (no loading, no blinking)
      // Always update - React will handle rendering based on activeTab
      if (data.symbols && Array.isArray(data.symbols)) {
        updatePricesFromSocket(data.symbols);
      }
    });

    priceSocketRef.current = priceSocket;
    
    // Load initial history data once
    loadHistory(true);
    
    // Periodically update latency values (even when prices don't change)
    latencyUpdateIntervalRef.current = setInterval(() => {
      setHistoryData(prevData => {
        return prevData.map(item => {
          if (item.lastUpdateTimestamp) {
            const newLatency = Math.max(0, Date.now() - item.lastUpdateTimestamp);
            // Only update if latency changed significantly (more than 100ms)
            if (Math.abs((item.latency || 0) - newLatency) > 100) {
              return {
                ...item,
                latency: newLatency
              };
            }
          }
          return item;
        });
      });
    }, 500); // Update every 500ms for smooth latency display
    
    return () => {
      // Cleanup on unmount
      if (priceSocketRef.current) {
        priceSocketRef.current.off('crypto_price_updates');
        priceSocketRef.current.disconnect();
        priceSocketRef.current = null;
      }
      
      if (statsIntervalRef.current) {
        clearInterval(statsIntervalRef.current);
      }
      if (historySaveIntervalRef.current) {
        clearInterval(historySaveIntervalRef.current);
      }
      if (historyRefreshIntervalRef.current) {
        clearInterval(historyRefreshIntervalRef.current);
      }
      if (latencyUpdateIntervalRef.current) {
        clearInterval(latencyUpdateIntervalRef.current);
        latencyUpdateIntervalRef.current = null;
      }
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, []); // Run only once on mount

  
  // Load comparison data for selected instruments - use real-time data from historyData
  const loadComparisonData = useCallback(async (filterHours = null) => {
    if (selectedInstruments.length === 0) {
      alert('Please select at least one instrument to compare');
      return;
    }

    setComparisonLoading(true);
    try {
      // First, try to fetch historical data for symbols that don't have sufficient chartData
      const symbolsNeedingData = [];
      const allData = selectedInstruments.map(symbol => {
        const item = historyData.find(d => d.symbol === symbol);
        if (item) {
          // Use chartData if available and has multiple points
          if (item.chartData && item.chartData.length > 1) {
            return {
              symbol,
              snapshots: item.chartData.map(point => ({
                timestamp: point.timestamp || Date.now(),
                price: point.price || item.price || 0
              }))
            };
          } else {
            // Need to fetch historical data
            symbolsNeedingData.push(symbol);
            // Use current price as placeholder
            return {
              symbol,
              snapshots: item.price > 0 ? [{
                timestamp: item.lastUpdateTimestamp || Date.now(),
                price: item.price
              }] : []
            };
          }
        } else {
          symbolsNeedingData.push(symbol);
          return { symbol, snapshots: [] };
        }
      });

      // Fetch historical data for symbols that need it
      if (symbolsNeedingData.length > 0 && exchange !== 'global') {
        await Promise.all(symbolsNeedingData.map(async (symbol) => {
          try {
            const historyResponse = await fetch(
              `${API_BASE_URL}/api/realtime-history/get?symbol=${symbol}&hours=24`
            );
            if (historyResponse.ok) {
              const historyResult = await historyResponse.json();
              if (historyResult.snapshots && historyResult.snapshots.length > 0) {
                const currentTime = Date.now();
                const twentyFourHoursAgo = currentTime - (24 * 60 * 60 * 1000);
                const filteredSnapshots = historyResult.snapshots
                  .filter(s => s.timestamp >= twentyFourHoursAgo)
                  .sort((a, b) => a.timestamp - b.timestamp);
                
                // Sample every 10 minutes for better chart resolution
                const sampleInterval = 10 * 60 * 1000;
                let lastSampledTime = 0;
                const sampledSnapshots = [];
                
                filteredSnapshots.forEach(snapshot => {
                  if (snapshot.timestamp - lastSampledTime >= sampleInterval || sampledSnapshots.length === 0) {
                    sampledSnapshots.push({
                      timestamp: snapshot.timestamp,
                      price: snapshot.price
                    });
                    lastSampledTime = snapshot.timestamp;
                  }
                });
                
                // Update the data for this symbol
                const dataIndex = allData.findIndex(d => d.symbol === symbol);
                if (dataIndex >= 0 && sampledSnapshots.length > 0) {
                  allData[dataIndex].snapshots = sampledSnapshots;
                }
              }
            }
          } catch (error) {
            console.error(`Error loading history for ${symbol}:`, error);
          }
        }));
      }

      // If we still don't have enough data points, create synthetic data points over time
      // This ensures the graph shows variation even with limited data
      allData.forEach(({ symbol, snapshots }) => {
        const item = historyData.find(d => d.symbol === symbol);
        if (!item || item.price <= 0) return;

        if (snapshots.length === 0) {
          // Create data points over the last hour using change percentages to show variation
          const now = Date.now();
          const oneHourAgo = now - (60 * 60 * 1000);
          const syntheticSnapshots = [];
          const change1h = item.change1h || 0;
          
          // Create points that show the price evolution over the last hour
          // Use change1h to create a linear progression from start to current
          for (let time = oneHourAgo; time <= now; time += 5 * 60 * 1000) {
            const progress = (time - oneHourAgo) / (now - oneHourAgo); // 0 to 1
            // Calculate price at this point: start with price that would result in current change1h
            const startPrice = item.price / (1 + change1h / 100);
            const priceAtTime = startPrice * (1 + (change1h * progress) / 100);
            syntheticSnapshots.push({
              timestamp: time,
              price: priceAtTime
            });
          }
          snapshots.push(...syntheticSnapshots);
        } else if (snapshots.length === 1) {
          // If only one point, create synthetic progression using change percentages
          const singlePoint = snapshots[0];
          const now = Date.now();
          const oneHourAgo = now - (60 * 60 * 1000);
          const change1h = item.change1h || 0;
          const newSnapshots = [];
          
          // Create points showing price evolution
          for (let time = oneHourAgo; time <= now; time += 5 * 60 * 1000) {
            const progress = (time - oneHourAgo) / (now - oneHourAgo);
            const startPrice = item.price / (1 + change1h / 100);
            const priceAtTime = startPrice * (1 + (change1h * progress) / 100);
            newSnapshots.push({
              timestamp: time,
              price: priceAtTime
            });
          }
          snapshots.length = 0;
          snapshots.push(...newSnapshots);
        } else if (snapshots.length > 1) {
          // If we have multiple points but they're all the same price, add variation
          const prices = snapshots.map(s => s.price);
          const allSame = prices.every(p => Math.abs(p - prices[0]) < 0.01);
          if (allSame && item.change1h) {
            // Add variation based on change1h
            const sortedSnapshots = [...snapshots].sort((a, b) => a.timestamp - b.timestamp);
            const firstPrice = sortedSnapshots[0].price;
            const lastPrice = sortedSnapshots[sortedSnapshots.length - 1].price;
            const timeSpan = sortedSnapshots[sortedSnapshots.length - 1].timestamp - sortedSnapshots[0].timestamp;
            
            // Recalculate prices with variation
            sortedSnapshots.forEach((snapshot, index) => {
              if (timeSpan > 0) {
                const progress = (snapshot.timestamp - sortedSnapshots[0].timestamp) / timeSpan;
                const change1h = item.change1h || 0;
                const startPrice = lastPrice / (1 + change1h / 100);
                snapshot.price = startPrice * (1 + (change1h * progress) / 100);
              }
            });
            
            snapshots.length = 0;
            snapshots.push(...sortedSnapshots);
          }
        }
      });

      // Store initial prices (first price for each symbol) for percentage calculation
      const initialPricesMap = {};
      allData.forEach(({ symbol, snapshots }) => {
        if (snapshots.length > 0) {
          // Get the first (oldest) price as baseline
          const sortedSnapshots = [...snapshots].sort((a, b) => a.timestamp - b.timestamp);
          initialPricesMap[symbol] = sortedSnapshots[0].price;
        } else {
          // If no snapshots, use current price from historyData as initial price
          const item = historyData.find(d => d.symbol === symbol);
          if (item && item.price > 0) {
            initialPricesMap[symbol] = item.price;
          }
        }
      });
      setInitialPrices(initialPricesMap);

      // Combine all data into a single dataset for comparison
      // Create a map of timestamps to prices for each symbol
      const timeMap = new Map();
      
      allData.forEach(({ symbol, snapshots }) => {
        snapshots.forEach(snapshot => {
          const timestamp = snapshot.timestamp;
          const date = new Date(timestamp);
          // Format time based on filter - use user's local timezone
          let currentFilter;
          if (filterHours && typeof filterHours === 'number') {
            currentFilter = filterHours;
          } else {
            currentFilter = timeFilter === '1h' ? 1 : timeFilter === '6h' ? 6 : 24;
          }
          currentFilter = Number(currentFilter) || 24;
          const time = currentFilter <= 1 
            ? date.toLocaleString([], { hour: '2-digit', minute: '2-digit', hour12: false })
            : date.toLocaleString([], { 
                month: '2-digit', 
                day: '2-digit', 
                hour: '2-digit', 
                minute: '2-digit',
                hour12: false 
              });
          
          if (!timeMap.has(timestamp)) {
            timeMap.set(timestamp, { time, timestamp, fullTime: date });
          }
          
          const dataPoint = timeMap.get(timestamp);
          const initialPrice = initialPricesMap[symbol];
          
          // Calculate percentage change from initial price
          if (initialPrice && initialPrice > 0) {
            const percentChange = ((snapshot.price - initialPrice) / initialPrice) * 100;
            dataPoint[`${symbol}_price`] = snapshot.price; // Keep price for tooltip
            dataPoint[symbol] = parseFloat(percentChange.toFixed(2)); // Percentage change
          } else {
            dataPoint[symbol] = 0;
          }
        });
      });

      // Convert to array and sort by timestamp, keeping timestamp for filtering
      let allDataWithTimestamp = Array.from(timeMap.values())
        .sort((a, b) => a.timestamp - b.timestamp);

      // Forward-fill so every timestamp has every symbol
      allDataWithTimestamp = fillComparisonData(allDataWithTimestamp, selectedInstruments);

      // If no data points from chart data, create initial data points from current prices
      if (allDataWithTimestamp.length === 0) {
        const now = Date.now();
        const date = new Date(now);
        const currentFilter = timeFilter === '1h' ? 1 : timeFilter === '6h' ? 6 : 24;
        const time = currentFilter <= 1 
          ? date.toLocaleString([], { hour: '2-digit', minute: '2-digit', hour12: false })
          : date.toLocaleString([], { 
              month: '2-digit', 
              day: '2-digit', 
              hour: '2-digit', 
              minute: '2-digit',
              hour12: false 
            });
        
        const initialPoint = { time, timestamp: now, fullTime: date };
        selectedInstruments.forEach(symbol => {
          const item = historyData.find(d => d.symbol === symbol);
          if (item && item.price > 0 && initialPricesMap[symbol]) {
            const percentChange = ((item.price - initialPricesMap[symbol]) / initialPricesMap[symbol]) * 100;
            initialPoint[`${symbol}_price`] = item.price;
            initialPoint[symbol] = parseFloat(percentChange.toFixed(2));
          }
        });
        allDataWithTimestamp = [initialPoint];
      }

      // Store all data
      setAllComparisonData(allDataWithTimestamp);

      // Apply time filter
      let currentFilter;
      if (filterHours && typeof filterHours === 'number') {
        currentFilter = filterHours;
      } else {
        currentFilter = timeFilter === '1h' ? 1 : timeFilter === '6h' ? 6 : 24;
      }
      currentFilter = Number(currentFilter) || 24;
      const now = Date.now();
      const filterTime = currentFilter * 60 * 60 * 1000; // Convert hours to milliseconds
      const cutoffTime = now - filterTime;

      const filteredData = fillComparisonData(allDataWithTimestamp, selectedInstruments)
        .filter(item => item.timestamp >= cutoffTime)
        .map(item => {
          const { timestamp, fullTime, ...rest } = item;
          return rest;
        });

      setComparisonData(filteredData);
    } catch (error) {
      console.error('Error loading comparison data:', error);
      alert('Failed to load comparison data');
    } finally {
      setComparisonLoading(false);
    }
  }, [selectedInstruments, historyData, timeFilter]);

  // Auto-load comparison when instruments are selected or tab is switched to compare
  useEffect(() => {
    if (activeTab === 'compare' && selectedInstruments.length > 0 && historyData.length > 0) {
      // Auto-load comparison data from real-time historyData immediately
      loadComparisonData();
    }
  }, [activeTab, selectedInstruments, historyData.length, loadComparisonData]);

  // Apply time filter when it changes - update comparison data in real-time
  useEffect(() => {
    if (allComparisonData.length > 0) {
      const currentFilter = timeFilter === '1h' ? 1 : timeFilter === '6h' ? 6 : 24;
      const now = Date.now();
      const filterTime = currentFilter * 60 * 60 * 1000;
      const cutoffTime = now - filterTime;

      const filteredData = allComparisonData
        .filter(item => item.timestamp >= cutoffTime)
        .map(item => {
          const { timestamp, fullTime, ...rest } = item;
          return rest;
        });

      setComparisonData(filteredData);
    }
  }, [timeFilter, allComparisonData]);

  // Update comparison data in real-time when prices update from WebSocket
  useEffect(() => {
    // Only update if we have initial prices set (from loadComparisonData)
    if (activeTab === 'compare' && selectedInstruments.length > 0 && historyData.length > 0 && Object.keys(initialPrices).length > 0) {
      // Rebuild comparison data from real-time historyData chartData
      const allData = selectedInstruments.map(symbol => {
        const item = historyData.find(d => d.symbol === symbol);
        if (item) {
          // Use chartData if available, otherwise use current price
          if (item.chartData && item.chartData.length > 0) {
            return {
              symbol,
              snapshots: item.chartData.map(point => ({
                timestamp: point.timestamp || Date.now(),
                price: point.price || item.price || 0
              }))
            };
          } else if (item.price > 0) {
            // If no chart data but we have current price, create a data point
            return {
              symbol,
              snapshots: [{
                timestamp: item.lastUpdateTimestamp || Date.now(),
                price: item.price
              }]
            };
          }
        }
        return { symbol, snapshots: [] };
      });

      // Create time map for all data points
      const timeMap = new Map();
      const initialPricesMap = { ...initialPrices };
      
      allData.forEach(({ symbol, snapshots }) => {
        snapshots.forEach(snapshot => {
          const timestamp = snapshot.timestamp;
          const date = new Date(timestamp);
          const currentFilter = timeFilter === '1h' ? 1 : timeFilter === '6h' ? 6 : 24;
          const time = currentFilter <= 1 
            ? date.toLocaleString([], { hour: '2-digit', minute: '2-digit', hour12: false })
            : date.toLocaleString([], { 
                month: '2-digit', 
                day: '2-digit', 
                hour: '2-digit', 
                minute: '2-digit',
                hour12: false 
              });
          
          if (!timeMap.has(timestamp)) {
            timeMap.set(timestamp, { time, timestamp, fullTime: date });
          }
          
          const dataPoint = timeMap.get(timestamp);
          const initialPrice = initialPricesMap[symbol];
          
          // Calculate percentage change from initial price
          if (initialPrice && initialPrice > 0) {
            const percentChange = ((snapshot.price - initialPrice) / initialPrice) * 100;
            dataPoint[`${symbol}_price`] = snapshot.price;
            dataPoint[symbol] = parseFloat(percentChange.toFixed(2));
          } else {
            dataPoint[symbol] = 0;
          }
        });
      });

      // Convert to array and sort by timestamp
      let allDataWithTimestamp = Array.from(timeMap.values())
        .sort((a, b) => a.timestamp - b.timestamp);

      // Forward-fill missing values for all symbols
      allDataWithTimestamp = fillComparisonData(allDataWithTimestamp, selectedInstruments);

      // Store all data
      setAllComparisonData(allDataWithTimestamp);

      // Apply time filter
      const currentFilter = timeFilter === '1h' ? 1 : timeFilter === '6h' ? 6 : 24;
      const now = Date.now();
      const filterTime = currentFilter * 60 * 60 * 1000;
      const cutoffTime = now - filterTime;

      const filteredData = fillComparisonData(allDataWithTimestamp, selectedInstruments)
        .filter(item => item.timestamp >= cutoffTime)
        .map(item => {
          const { timestamp, fullTime, ...rest } = item;
          return rest;
        });

      setComparisonData(filteredData);
    }
  }, [historyData, activeTab, selectedInstruments, initialPrices, timeFilter]);

  // Load crypto list data with chart data (only on initial load)
  const loadHistory = async (showLoading = false) => {
    // For the global visualization view we don't need the backend
    // /api/realtime-history/list endpoint (which may not exist),
    // so we skip this call entirely to avoid 404 popups.
    if (exchange === 'global') {
      return;
    }

    try {
      if (showLoading) {
        setHistoryLoading(true);
      }
      
      const response = await fetch(`${API_BASE_URL}/api/realtime-history/list`);
      
      if (!response.ok) {
        // Gracefully handle missing history endpoint without breaking the UI
        if (response.status === 404) {
          console.warn('History endpoint /api/realtime-history/list not found (404). Skipping history load.');
          return;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.symbols && result.symbols.length > 0) {
        // Only fetch chart data on initial load or if cache is empty
        const shouldFetchCharts = showLoading || Object.keys(chartDataCacheRef.current).length === 0;
        
        const cryptoListWithCharts = await Promise.all(
          result.symbols.map(async (symbolInfo) => {
            // Use cached chart data if available, only fetch on initial load
            let chartData = chartDataCacheRef.current[symbolInfo.symbol] || [];
            
            // Always try to fetch chart data if not in cache
            if (!chartDataCacheRef.current[symbolInfo.symbol]) {
              try {
                const historyResponse = await fetch(
                  `${API_BASE_URL}/api/realtime-history/get?symbol=${symbolInfo.symbol}&hours=12`
                );
                const historyResult = await historyResponse.json();
                
                if (historyResult.snapshots && historyResult.snapshots.length > 0) {
                  // Format snapshots for chart
                  const currentTime = Date.now();
                  const twelveHoursAgo = currentTime - (12 * 60 * 60 * 1000);
                  const filteredSnapshots = historyResult.snapshots.filter(
                    s => s.timestamp >= twelveHoursAgo
                  );
                  
                  // Sample every 5 minutes for better chart resolution
                  const sampleInterval = 5 * 60 * 1000; // 5 minutes
                  let lastSampledTime = 0;
                  
                  filteredSnapshots.forEach(snapshot => {
                    if (snapshot.timestamp - lastSampledTime >= sampleInterval || chartData.length === 0) {
                      chartData.push({
                        time: new Date(snapshot.timestamp).toLocaleTimeString(),
                        price: snapshot.price,
                        timestamp: snapshot.timestamp
                      });
                      lastSampledTime = snapshot.timestamp;
                    }
                  });
                  
                  // Cache the chart data
                  if (chartData.length > 0) {
                    chartDataCacheRef.current[symbolInfo.symbol] = chartData;
                  }
                }
                
                // If we have a current price but no historical data, create a simple chart
                if (chartData.length === 0 && symbolInfo.current_price > 0) {
                  const now = Date.now();
                  // Create a simple flat chart with current price
                  for (let i = 0; i < 20; i++) {
                    chartData.push({
                      time: new Date(now - (20 - i) * 60000).toLocaleTimeString(),
                      price: symbolInfo.current_price,
                      timestamp: now - (20 - i) * 60000
                    });
                  }
                  chartDataCacheRef.current[symbolInfo.symbol] = chartData;
                }
              } catch (error) {
                console.error(`Error loading chart data for ${symbolInfo.symbol}:`, error);
                // On error, create a simple chart with current price if available
                if (symbolInfo.current_price > 0) {
                  const now = Date.now();
                  for (let i = 0; i < 20; i++) {
                    chartData.push({
                      time: new Date(now - (20 - i) * 60000).toLocaleTimeString(),
                      price: symbolInfo.current_price,
                      timestamp: now - (20 - i) * 60000
                    });
                  }
                  chartDataCacheRef.current[symbolInfo.symbol] = chartData;
                }
              }
            } else {
              // Use cached data
              chartData = chartDataCacheRef.current[symbolInfo.symbol];
            }
            
            // Calculate latency (time since last update in milliseconds)
            const latency = symbolInfo.last_update 
              ? Math.max(0, Date.now() - symbolInfo.last_update)
              : null;
            
            return {
              symbol: symbolInfo.symbol,
              name: symbolInfo.name || symbolInfo.symbol,
              price: symbolInfo.current_price !== undefined && symbolInfo.current_price !== null ? symbolInfo.current_price : 0,
              change1h: symbolInfo.change1h !== undefined && symbolInfo.change1h !== null ? symbolInfo.change1h : 0,
              change6h: symbolInfo.change6h !== undefined && symbolInfo.change6h !== null ? symbolInfo.change6h : 0,
              change12h: symbolInfo.change12h !== undefined && symbolInfo.change12h !== null ? symbolInfo.change12h : 0,
              latency: latency,
              lastUpdateTimestamp: symbolInfo.last_update || null,
              chartData: chartData
            };
          })
        );
        
        // Update state smoothly - only update changed values to prevent blinking
        setHistoryData(prevData => {
          // If no previous data, just set new data
          if (prevData.length === 0) {
            return cryptoListWithCharts;
          }
          
          // Create a map for quick lookup
          const prevMap = new Map(prevData.map(item => [item.symbol, item]));
          
          // Check if any values actually changed
          let hasChanges = false;
          const updatedData = cryptoListWithCharts.map(newItem => {
            const prevItem = prevMap.get(newItem.symbol);
            if (prevItem) {
              // Only update if price or changes actually changed (with small tolerance for floating point)
              const priceChanged = Math.abs(prevItem.price - newItem.price) > 0.01;
              const change1hChanged = Math.abs(prevItem.change1h - newItem.change1h) > 0.01;
              const change6hChanged = Math.abs(prevItem.change6h - newItem.change6h) > 0.01;
              const change12hChanged = Math.abs(prevItem.change12h - newItem.change12h) > 0.01;
              
              if (priceChanged || change1hChanged || change6hChanged || change12hChanged) {
                hasChanges = true;
                return newItem;
              }
              // Keep previous item if no changes (preserves React keys and prevents re-render)
              return prevItem;
            }
            hasChanges = true;
            return newItem;
          });
          
          return hasChanges ? updatedData : prevData;
        });
      } else {
        console.warn('No symbols found in response from history API:', result);
        // Keep existing data if any; do not force empty state
        setHistoryData(prev => prev.length > 0 ? prev : []);
      }
    } catch (error) {
      console.error('Error loading crypto list:', error);
      // Avoid noisy alerts for missing/non-critical endpoints; log only
      // Keep existing data if available, otherwise set empty
      setHistoryData(prev => prev.length > 0 ? prev : []);
    } finally {
      if (showLoading) {
        setHistoryLoading(false);
      }
    }
  };

  // Save price snapshot to history
  const savePriceSnapshot = async (price, symbol) => {
    if (!price || price <= 0) return;
    
    try {
      await fetch(`${API_BASE_URL}/api/realtime-history/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: symbol || 'BTCUSDT',
          price: price
        })
      });
    } catch (error) {
      console.error('Error saving price snapshot:', error);
    }
  };

  const connect = async () => {
    try {
      // Connect to SocketIO server with proper configuration
      const socket = io(SOCKET_URL, {
        transports: ['polling', 'websocket'], // Try polling first, then websocket
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 5,
        timeout: 20000,
        forceNew: true
      });

      socket.on('connect', () => {
        console.log('SocketIO connected');
        setIsConnected(true);
      });

      socket.on('connect_error', (error) => {
        console.error('SocketIO connection error:', error);
        alert(`Connection error: ${error.message || 'Failed to connect'}`);
      });

      socket.on('disconnect', (reason) => {
        console.log('SocketIO disconnected:', reason);
        setIsConnected(false);
      });

      socketRef.current = socket;

      // Wait a bit for SocketIO to establish connection
      await new Promise(resolve => setTimeout(resolve, 500));

      // Start WebSocket connection via REST API
      const requestBody = {
        exchange: exchange
      };
      
      if (exchange === 'okx') {
        requestBody.channel = channel;
        requestBody.inst_id = instId;
      } else if (exchange === 'binance') {
        requestBody.symbol = symbol;
        requestBody.stream_type = streamType;
      } else if (exchange === 'custom') {
        if (!customWebsocketUrl.trim()) {
          throw new Error('Please enter a WebSocket URL');
        }
        requestBody.websocket_url = customWebsocketUrl.trim();
        if (subscribeMessage.trim()) {
          try {
            // Validate JSON if provided
            const parsed = JSON.parse(subscribeMessage.trim());
            requestBody.subscribe_message = parsed;
          } catch (e) {
            throw new Error('Subscribe message must be valid JSON');
          }
        }
      }
      
      const response = await fetch(`${API_BASE_URL}/api/websocket/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });

      const result = await response.json();
      
      if (!response.ok) {
        throw new Error(result.error || 'Failed to connect');
      }

      const newConnectionId = result.connection_id;
      setConnectionId(newConnectionId);
      currentConnectionIdRef.current = newConnectionId;
      
      // Set up listener for crypto data with the correct connection_id
      socket.off('crypto_data'); // Remove any old listeners
      socket.on('crypto_data', (data) => {
        console.log('Received crypto data:', data);
        // Check if this data belongs to our connection
        if (data.connection_id === newConnectionId) {
          handleNewData(data.data);
        }
      });
      
      // Start interval to update stats every second (even if no new messages)
      statsIntervalRef.current = setInterval(() => {
        updateStats();
      }, 1000);
      // Reset stream data and stats when starting new connection
      setStreamData([]);
      setChartData([]);
      setStats({
        totalMessages: 0,
        messagesPerSecond: 0,
        lastUpdate: null
      });
      messageCountRef.current = 0;
      lastSecondRef.current = Date.now();
      lastDataTimestampRef.current = Date.now();
      
      // Start saving price snapshots every minute
      if (historySaveIntervalRef.current) {
        clearInterval(historySaveIntervalRef.current);
      }
      
      // Save immediately if we have a price
      if (lastPriceRef.current) {
        const currentSymbol = exchange === 'okx' ? instId.replace('-', '') : symbol;
        savePriceSnapshot(lastPriceRef.current, currentSymbol);
      }
      
      historySaveIntervalRef.current = setInterval(() => {
        if (lastPriceRef.current) {
          const currentSymbol = exchange === 'okx' ? instId.replace('-', '') : symbol;
          savePriceSnapshot(lastPriceRef.current, currentSymbol);
        }
      }, 60000); // Save every minute
      
    } catch (error) {
      console.error('Connection error:', error);
      alert(`Failed to connect: ${error.message}`);
    }
  };

  const disconnect = async () => {
    try {
      // Clear stats update interval
      if (statsIntervalRef.current) {
        clearInterval(statsIntervalRef.current);
        statsIntervalRef.current = null;
      }
      
      if (historySaveIntervalRef.current) {
        clearInterval(historySaveIntervalRef.current);
        historySaveIntervalRef.current = null;
      }
      
      if (historyRefreshIntervalRef.current) {
        clearInterval(historyRefreshIntervalRef.current);
        historyRefreshIntervalRef.current = null;
      }
      
      // Final stats update before disconnecting
      updateStats();
      
      if (connectionId) {
        await fetch(`${API_BASE_URL}/api/websocket/disconnect`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ connection_id: connectionId })
        });
      }
      
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
      
      setIsConnected(false);
      setConnectionId(null);
      currentConnectionIdRef.current = null;
    } catch (error) {
      console.error('Disconnect error:', error);
    }
  };

  const updateStats = () => {
    const now = Date.now();
    const elapsed = (now - lastSecondRef.current) / 1000;
    
    // Always update if we have messages or if 1 second has passed
    if (messageCountRef.current > 0 || elapsed >= 1) {
      setStats(prev => {
        // Total Messages = Previous Total + Messages received since last update
        const newTotal = prev.totalMessages + messageCountRef.current;
        const messagesPerSec = elapsed > 0 ? messageCountRef.current / elapsed : 0;
        
        return {
          ...prev,
          messagesPerSecond: messagesPerSec,
          totalMessages: newTotal,
          lastUpdate: new Date().toLocaleTimeString()
        };
      });
      
      // Reset counter for next period
      messageCountRef.current = 0;
      lastSecondRef.current = now;
    }
  };

  // Extract metrics from data for charting
  const extractMetrics = (data) => {
    const metrics = [];
    const now = Date.now();
    const timestamp = new Date(now).toLocaleTimeString();
    // Calculate latency (time since last data point)
    const latency = lastDataTimestampRef.current ? (now - lastDataTimestampRef.current) : 0;
    lastDataTimestampRef.current = now;
    
    // Handle OKX format: {"arg": {...}, "data": [...]}
    if (data && data.data && Array.isArray(data.data)) {
      data.data.forEach(item => {
        const metric = { time: timestamp, latency: latency };
        
        // OKX Trades format
        if (item.px && item.sz) {
          metric.price = parseFloat(item.px);
          metric.volume = parseFloat(item.sz);
          metric.side = item.side || 'N/A';
        }
        // OKX Tickers format
        else if (item.last) {
          metric.price = parseFloat(item.last);
          metric.volume24h = parseFloat(item.vol24h || 0);
          metric.high24h = parseFloat(item.high24h || 0);
          metric.low24h = parseFloat(item.low24h || 0);
        }
        // OKX Order Book format
        else if (item.bids && item.asks) {
          const bestBid = item.bids[0] ? parseFloat(item.bids[0][0]) : 0;
          const bestAsk = item.asks[0] ? parseFloat(item.asks[0][0]) : 0;
          metric.price = (bestBid + bestAsk) / 2;
          metric.bid = bestBid;
          metric.ask = bestAsk;
        }
        
        if (metric.price) {
          metrics.push(metric);
        }
      });
    }
    // Handle Binance format: {"symbol": "...", "stream_type": "...", "data": {...}}
    else if (data && data.data && typeof data.data === 'object') {
      const metric = { time: timestamp, latency: latency };
      const binanceData = data.data;
      
      // Binance Trade format
      if (binanceData.p && binanceData.q) {
        metric.price = parseFloat(binanceData.p);
        metric.volume = parseFloat(binanceData.q);
        metric.side = binanceData.m ? 'sell' : 'buy';
      }
      // Binance Ticker format
      else if (binanceData.c) {
        metric.price = parseFloat(binanceData.c);
        metric.volume24h = parseFloat(binanceData.v || 0);
        metric.high24h = parseFloat(binanceData.h || 0);
        metric.low24h = parseFloat(binanceData.l || 0);
      }
      
      if (metric.price) {
        metrics.push(metric);
      }
    }
    // Handle direct data object (Custom WebSocket)
    else if (data && typeof data === 'object') {
      const metric = { time: timestamp, latency: latency };
      
      if (data.price) metric.price = parseFloat(data.price);
      if (data.px) metric.price = parseFloat(data.px);
      if (data.last) metric.price = parseFloat(data.last);
      if (data.volume) metric.volume = parseFloat(data.volume);
      if (data.sz) metric.volume = parseFloat(data.sz);
      if (data.q) metric.volume = parseFloat(data.q);
      
      if (metric.price) {
        metrics.push(metric);
      }
    }
    
    return metrics;
  };

  const handleNewData = (data) => {
    // Count only valid trade data items (matching what gets saved to database)
    // This ensures frontend count matches database records
    let validTradeItems = 0;
    
    // Skip subscription confirmations and event messages
    if (data && data.event) {
      // This is a subscription confirmation, don't count it
      return;
    }
    
    // Count valid trade items (with required fields like px, sz for trades)
    if (data && data.data && Array.isArray(data.data)) {
      // OKX format: {"arg": {...}, "data": [...]}
      data.data.forEach(item => {
        // For trades channel, check if item has px and sz (required fields)
        if (item.px && item.sz) {
          validTradeItems += 1;
        }
        // For tickers channel, check if item has last
        else if (item.last) {
          validTradeItems += 1;
        }
        // For order book, check if item has bids and asks
        else if (item.bids && item.asks) {
          validTradeItems += 1;
        }
      });
    } else if (data && data.data && typeof data.data === 'object') {
      // Binance format: single trade object
      const binanceData = data.data;
      if ((binanceData.p && binanceData.q) || binanceData.c) {
        validTradeItems = 1;
      }
    }
    
    // Only count if we have valid trade items (matching database behavior)
    if (validTradeItems > 0) {
      messageCountRef.current += validTradeItems; // Count valid trade items, not messages
      
      // Update stats immediately
      const now = Date.now();
      const elapsed = (now - lastSecondRef.current) / 1000;
      
      setStats(prev => {
        const newTotal = prev.totalMessages + validTradeItems; // Count valid trade items
        const messagesPerSec = elapsed > 0 ? messageCountRef.current / elapsed : 0;
        return {
          ...prev,
          totalMessages: newTotal,
          messagesPerSecond: messagesPerSec,
          lastUpdate: new Date().toLocaleTimeString()
        };
      });
      
      // Reset counter and timer if 1 second has passed
      if (elapsed >= 1) {
        messageCountRef.current = 0;
        lastSecondRef.current = now;
      }
    }

    // Extract metrics for charts
    const metrics = extractMetrics(data);
    if (metrics.length > 0) {
      setChartData(prev => {
        const newChartData = [...prev, ...metrics].slice(-maxChartPoints);
        return newChartData;
      });
      
      // Update last price for history saving
      const latestPrice = metrics[metrics.length - 1]?.price;
      if (latestPrice) {
        const previousPrice = lastPriceRef.current;
        lastPriceRef.current = latestPrice;
        
        // Save immediately on first price
        if (!previousPrice) {
          const currentSymbol = exchange === 'okx' ? instId.replace('-', '') : symbol;
          savePriceSnapshot(latestPrice, currentSymbol);
        }
      }
    }

    // Add new data to stream - append to end (oldest first, newest last)
    setStreamData(prev => {
      const newData = [...prev, data].slice(-maxDisplayItems); // Keep last N items
      
      // Don't auto-scroll - let user control scroll position
      
      // Notify parent component if callback provided
      if (onDataCollected) {
        onDataCollected(newData);
      }
      
      return newData;
    });
  };

  const clearData = async () => {
    if (connectionId) {
      try {
        await fetch(`${API_BASE_URL}/api/websocket/clear/${connectionId}`, {
          method: 'POST'
        });
        setStreamData([]);
        setChartData([]);
        setStats({
          totalMessages: 0,
          messagesPerSecond: 0,
          lastUpdate: null
        });
      } catch (error) {
        console.error('Clear error:', error);
      }
    }
  };

  const exportData = () => {
    if (streamData.length === 0) {
      alert('No data to export');
      return;
    }

    const jsonStr = JSON.stringify(streamData, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `crypto_stream_${connectionId}_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="realtime-stream">
      {/* Header removed - no title, tabs, or buttons for any tab */}

      {activeTab === 'live' && !isConnected && (
        <div className="stream-config">
          <div className="config-group">
            <label>Exchange:</label>
            <select value={exchange} onChange={(e) => handleExchangeChange(e.target.value)} className="crypto-select">
              <option value="okx">OKX</option>
              <option value="binance">Binance</option>
              <option value="custom">Custom WebSocket</option>
            </select>
          </div>
          
          {exchange === 'custom' ? (
            <>
              <div className="config-group" style={{ flex: '1 1 100%' }}>
                <label>WebSocket URL:</label>
                <input
                  type="text"
                  value={customWebsocketUrl}
                  onChange={(e) => setCustomWebsocketUrl(e.target.value)}
                  placeholder="wss://example.com/ws"
                />
              </div>
              <div className="config-group" style={{ flex: '1 1 100%' }}>
                <label>Subscribe Message (Optional JSON):</label>
                <textarea
                  value={subscribeMessage}
                  onChange={(e) => setSubscribeMessage(e.target.value)}
                  placeholder='{"op": "subscribe", "args": [...]}'
                  rows="3"
                  className="subscribe-message-input"
                />
              </div>
            </>
          ) : exchange === 'okx' ? (
            <>
              <div className="config-group">
                <label>Channel:</label>
                <select value={channel} onChange={(e) => setChannel(e.target.value)} className="crypto-select">
                  <option value="trades">Trades</option>
                  <option value="tickers">Tickers</option>
                  <option value="books5">Order Book (5 levels)</option>
                  <option value="books">Order Book (Full)</option>
                </select>
              </div>
              <div className="config-group">
                <label>Instrument:</label>
                <select
                  value={instId}
                  onChange={(e) => setInstId(e.target.value)}
                  className="crypto-select"
                >
                  {TRACKED_CRYPTO_SYMBOLS.map((sym) => {
                    const okxFormat = convertToOKXFormat(sym);
                    const cryptoInfo = CRYPTO_NAMES[sym] || { name: sym, symbol: sym.replace('USDT', '') };
                    return (
                      <option key={sym} value={okxFormat}>
                        {cryptoInfo.name} {cryptoInfo.symbol} ({okxFormat})
                      </option>
                    );
                  })}
                </select>
              </div>
            </>
          ) : (
            <>
              <div className="config-group">
                <label>Stream Type:</label>
                <select value={streamType} onChange={(e) => setStreamType(e.target.value)} className="crypto-select">
                  <option value="trade">Trade</option>
                  <option value="ticker">Ticker</option>
                  <option value="depth">Depth</option>
                </select>
              </div>
              <div className="config-group">
                <label>Symbol:</label>
                <select
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  className="crypto-select"
                >
                  {TRACKED_CRYPTO_SYMBOLS.map((sym) => {
                    const cryptoInfo = CRYPTO_NAMES[sym] || { name: sym, symbol: sym.replace('USDT', '') };
                    return (
                      <option key={sym} value={sym}>
                        {cryptoInfo.name} {cryptoInfo.symbol} ({sym})
                      </option>
                    );
                  })}
                </select>
              </div>
            </>
          )}
        </div>
      )}

      {activeTab === 'live' && isConnected && (
        <div className="stream-stats">
          <div className="stat-item">
            <span className="stat-label">Status:</span>
            <span className="stat-value status-connected">● Live</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Exchange:</span>
            <span className="stat-value" title="Currently connected exchange">
              {exchange === 'okx' ? 'OKX' : exchange === 'binance' ? 'Binance' : 'Custom WebSocket'}
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Instrument:</span>
            <span className="stat-value" title="Currently streaming instrument">
              {(() => {
                const cryptoInfo = CRYPTO_NAMES[symbol] || { name: symbol, symbol: symbol.replace('USDT', '') };
                return `${cryptoInfo.name} (${cryptoInfo.symbol})`;
              })()}
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Total Messages:</span>
            <span className="stat-value" title="Total messages received since stream started (updates every second)">
              {stats.totalMessages.toLocaleString()}
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Messages/sec:</span>
            <span className="stat-value" title="Current rate of messages per second">
              {stats.messagesPerSecond.toFixed(1)}
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Last Update:</span>
            <span className="stat-value">{stats.lastUpdate || 'N/A'}</span>
          </div>
          {chartData.length > 0 && (
            <div className="view-toggle-inline">
              <button
                className={viewMode === 'charts' ? 'active' : ''}
                onClick={() => setViewMode('charts')}
              >
                Charts
              </button>
              <button
                className={viewMode === 'raw' ? 'active' : ''}
                onClick={() => setViewMode('raw')}
              >
                📄 Raw Data
              </button>
            </div>
          )}
        </div>
      )}
      
      {activeTab === 'live' && !isConnected && streamData.length > 0 && (
        <div className="stream-stats">
          <div className="stat-item">
            <span className="stat-label">Status:</span>
            <span className="stat-value">● Stopped</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Total Messages:</span>
            <span className="stat-value" title="Total messages collected during the last stream session">
              {stats.totalMessages.toLocaleString()}
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Data Points:</span>
            <span className="stat-value">{streamData.length.toLocaleString()}</span>
          </div>
          {chartData.length > 0 && (
            <div className="view-toggle-inline">
              <button
                className={viewMode === 'charts' ? 'active' : ''}
                onClick={() => setViewMode('charts')}
              >
                Charts
              </button>
              <button
                className={viewMode === 'raw' ? 'active' : ''}
                onClick={() => setViewMode('raw')}
              >
                📄 Raw Data
              </button>
            </div>
          )}
        </div>
      )}

      {activeTab === 'live' && viewMode === 'charts' && chartData.length > 0 && (
        <div className="charts-container">
          <div className="chart-wrapper premium-chart">
            <div className="chart-header">
              <h4>Price Analysis</h4>
              <div className="chart-stats">
                {chartData.length > 0 && (
                  <>
                    <span className="stat-badge">
                      Current: ${chartData[chartData.length - 1]?.price?.toFixed(2) || 'N/A'}
                    </span>
                    {chartData.length > 1 && (
                      <span className={`stat-badge ${(chartData[chartData.length - 1]?.price || 0) >= (chartData[0]?.price || 0) ? 'positive' : 'negative'}`}>
                        {((chartData[chartData.length - 1]?.price || 0) >= (chartData[0]?.price || 0) ? '↑' : '↓')} 
                        {chartData.length > 1 ? 
                          (((chartData[chartData.length - 1]?.price - chartData[0]?.price) / chartData[0]?.price) * 100).toFixed(2) + '%' 
                          : '0%'}
                      </span>
                    )}
                  </>
                )}
              </div>
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <AreaChart data={chartData} margin={{ top: 20, right: 30, left: 40, bottom: 40 }}>
                <defs>
                  <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3}/>
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.05}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" opacity={0.3} />
                <XAxis 
                  dataKey="time" 
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  stroke="#d1d5db"
                  strokeWidth={1}
                  interval={chartData.length > 20 ? Math.floor(chartData.length / 7) : chartData.length > 10 ? Math.floor(chartData.length / 5) : 0}
                />
                <YAxis 
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  stroke="#d1d5db"
                  strokeWidth={1}
                  width={70}
                  domain={['auto', 'auto']}
                  label={{ value: 'Price (USD)', angle: -90, position: 'insideLeft', style: { fill: '#6b7280', fontSize: 13, fontWeight: 500 } }}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'rgba(255, 255, 255, 0.98)', 
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
                    padding: '12px'
                  }}
                  labelStyle={{ color: '#111827', fontWeight: 600, fontSize: '12px', marginBottom: '8px' }}
                  itemStyle={{ fontSize: '12px', padding: '4px 0' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="price" 
                  stroke="#3b82f6" 
                  strokeWidth={2.5}
                  fill="url(#priceGradient)"
                  name="Price (USD)"
                  dot={false}
                  activeDot={{ r: 5, fill: '#3b82f6', strokeWidth: 2 }}
                  animationDuration={300}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {chartData.some(d => d.bid && d.ask) && (
            <div className="chart-wrapper premium-chart">
              <div className="chart-header">
                <h4>Bid/Ask Spread Analysis</h4>
                <div className="chart-stats">
                  {chartData.length > 0 && (
                    <span className="stat-badge">
                      Spread: ${((chartData[chartData.length - 1]?.ask || 0) - (chartData[chartData.length - 1]?.bid || 0)).toFixed(4)}
                    </span>
                  )}
                </div>
              </div>
              <ResponsiveContainer width="100%" height={250}>
                <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="bidGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ff7300" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#ff7300" stopOpacity={0.1}/>
                    </linearGradient>
                    <linearGradient id="askGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00ff88" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#00ff88" stopOpacity={0.1}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e8e8e8" opacity={0.4} strokeWidth={1} />
                  <XAxis 
                    dataKey="time" 
                    tick={{ fontSize: 11, fill: '#666' }}
                    stroke="#999"
                    interval="preserveStartEnd"
                  />
                  <YAxis 
                    tick={{ fontSize: 11, fill: '#666' }}
                    stroke="#999"
                    domain={['auto', 'auto']}
                    label={{ value: 'Price (USD)', angle: -90, position: 'insideLeft', style: { fill: '#666' } }}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                      border: '1px solid #0ea5e9',
                      borderRadius: '8px',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
                    }}
                  />
                  <Legend wrapperStyle={{ paddingTop: '20px' }} />
                  <Area
                    type="monotone"
                    dataKey="bid"
                    stroke="#ff7300"
                    strokeWidth={2}
                    fill="url(#bidGradient)"
                    name="Bid Price"
                    dot={false}
                    activeDot={{ r: 5 }}
                    animationDuration={300}
                  />
                  <Area
                    type="monotone"
                    dataKey="ask"
                    stroke="#00ff88"
                    strokeWidth={2}
                    fill="url(#askGradient)"
                    name="Ask Price"
                    dot={false}
                    activeDot={{ r: 5 }}
                    animationDuration={300}
                  />
                  <Line
                    type="monotone"
                    dataKey="price"
                    stroke="#0ea5e9"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    name="Mid Price"
                    dot={false}
                    animationDuration={300}
                  />
                  <Brush dataKey="time" height={30} stroke="#0ea5e9" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {chartData.some(d => d.high24h && d.low24h) && (
            <div className="chart-wrapper premium-chart">
              <div className="chart-header">
                <h4>24-Hour Range Analysis</h4>
                <div className="chart-stats">
                  {chartData.length > 0 && (
                    <>
                      <span className="stat-badge positive">
                        High: ${Math.max(...chartData.filter(d => d.high24h).map(d => d.high24h)).toFixed(2)}
                      </span>
                      <span className="stat-badge negative">
                        Low: ${Math.min(...chartData.filter(d => d.low24h).map(d => d.low24h)).toFixed(2)}
                      </span>
                    </>
                  )}
                </div>
              </div>
              <ResponsiveContainer width="100%" height={250}>
                <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="highGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ff0000" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#ff0000" stopOpacity={0.1}/>
                    </linearGradient>
                    <linearGradient id="lowGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0066ff" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#0066ff" stopOpacity={0.1}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e8e8e8" opacity={0.4} strokeWidth={1} />
                  <XAxis 
                    dataKey="time" 
                    tick={{ fontSize: 11, fill: '#666' }}
                    stroke="#999"
                    interval="preserveStartEnd"
                  />
                  <YAxis 
                    tick={{ fontSize: 11, fill: '#666' }}
                    stroke="#999"
                    domain={['auto', 'auto']}
                    label={{ value: 'Price (USD)', angle: -90, position: 'insideLeft', style: { fill: '#666' } }}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                      border: '1px solid #0ea5e9',
                      borderRadius: '8px',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
                    }}
                  />
                  <Legend wrapperStyle={{ paddingTop: '20px' }} />
                  <Area
                    type="monotone"
                    dataKey="high24h"
                    stroke="#ff0000"
                    strokeWidth={2}
                    fill="url(#highGradient)"
                    name="24h High"
                    dot={false}
                    activeDot={{ r: 5 }}
                    animationDuration={300}
                  />
                  <Area
                    type="monotone"
                    dataKey="low24h"
                    stroke="#0066ff"
                    strokeWidth={2}
                    fill="url(#lowGradient)"
                    name="24h Low"
                    dot={false}
                    activeDot={{ r: 5 }}
                    animationDuration={300}
                  />
                  <Line
                    type="monotone"
                    dataKey="price"
                    stroke="#0ea5e9"
                    strokeWidth={3}
                    name="Current Price"
                    dot={{ r: 4, fill: '#0ea5e9' }}
                    activeDot={{ r: 7, fill: '#0ea5e9', strokeWidth: 2 }}
                    animationDuration={300}
                  />
                  <Brush dataKey="time" height={30} stroke="#0ea5e9" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {chartData.some(d => d.latency !== undefined) && (
            <div className="chart-wrapper premium-chart">
              <div className="chart-header">
                <h4>Latency Analysis</h4>
                <div className="chart-stats">
                  {chartData.length > 0 && (() => {
                    const latencyData = chartData.filter(d => d.latency !== undefined);
                    const avgLatency = latencyData.length > 0 
                      ? latencyData.reduce((sum, d) => sum + (d.latency || 0), 0) / latencyData.length 
                      : 0;
                    const maxLatency = latencyData.length > 0
                      ? Math.max(...latencyData.map(d => d.latency || 0))
                      : 0;
                    return (
                      <>
                        <span className="stat-badge">
                          Avg: {avgLatency.toFixed(2)}ms
                        </span>
                        <span className="stat-badge">
                          Max: {maxLatency.toFixed(2)}ms
                        </span>
                      </>
                    );
                  })()}
                </div>
              </div>
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={chartData} margin={{ top: 20, right: 30, left: 40, bottom: 40 }}>
                  <defs>
                    <linearGradient id="latencyGradientFull" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ef4444" stopOpacity={0.3}/>
                      <stop offset="100%" stopColor="#ef4444" stopOpacity={0.05}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" opacity={0.3} />
                  <XAxis 
                    dataKey="time" 
                    tick={{ fontSize: 12, fill: '#6b7280' }}
                    stroke="#d1d5db"
                    strokeWidth={1}
                    interval={Math.floor(chartData.length / 6) || 0}
                  />
                  <YAxis 
                    tick={{ fontSize: 12, fill: '#6b7280' }}
                    stroke="#d1d5db"
                    strokeWidth={1}
                    width={70}
                    domain={['auto', 'auto']}
                    label={{ value: 'Latency (ms)', angle: -90, position: 'insideLeft', style: { fill: '#6b7280', fontSize: 13, fontWeight: 500 } }}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'rgba(255, 255, 255, 0.98)', 
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
                      padding: '12px'
                    }}
                    labelStyle={{ color: '#111827', fontWeight: 600, fontSize: '12px', marginBottom: '8px' }}
                    itemStyle={{ fontSize: '12px', padding: '4px 0' }}
                    formatter={(value) => `${value.toFixed(2)}ms`}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="latency" 
                    stroke="#ef4444" 
                    strokeWidth={2.5}
                    fill="url(#latencyGradientFull)"
                    name="Latency (ms)"
                    dot={false}
                    activeDot={{ r: 5, fill: '#ef4444', strokeWidth: 2 }}
                    animationDuration={300}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {activeTab === 'live' && viewMode === 'raw' && (
        <div className="stream-display">
          <div className="stream-list">
            {streamData.length === 0 ? (
              <div className="no-data">
                {isConnected ? 'Waiting for data...' : 'Click "Start Stream" to begin receiving real-time data'}
              </div>
            ) : (
              streamData.map((item, index) => (
                <div key={index} className="stream-item">
                  <pre>{JSON.stringify(item, null, 2)}</pre>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {activeTab === 'live' && viewMode === 'charts' && chartData.length === 0 && streamData.length === 0 && (
        <div className="stream-display">
          <div className="no-data">
            {isConnected ? 'Waiting for data...' : 'Click "Start Stream" to begin receiving real-time data'}
          </div>
        </div>
      )}

      {activeTab === 'list' && (
        <div className="history-container">
          <div className="history-header">
            <div className="history-header-actions">
              {historyLoading && (
                <span className="loading-indicator">⏳ Loading...</span>
              )}
              {/* Only show refresh button if not using props data */}
              {!websocketData && !messages && (
                <button 
                  className="refresh-btn" 
                  onClick={() => loadHistory(true)}
                  title="Refresh crypto list"
                >
                  🔄 Refresh
                </button>
              )}
            </div>
          </div>
          
          {historyLoading ? (
            <div className="no-data">Loading crypto list...</div>
          ) : !historyData || historyData.length === 0 ? (
            <div className="no-data">
              <p>No crypto data available.</p>
              <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: '8px' }}>
                The data will load automatically. If it doesn't appear, click "Refresh" or start a stream to begin collecting price data.
              </p>
            </div>
          ) : (
            <>
              {/* Market Down Ticket Cards */}
              {(() => {
                // Filter cryptos that have red graphs (downward trend in chart data)
                // This matches the logic used in the list view to determine graph color
                const marketDownCryptos = historyData
                  .filter(item => {
                    if (!item.price || item.price <= 0) return false;
                    
                    // Get chart data (same logic as list view)
                    let chartDataToUse = item.chartData || chartDataCacheRef.current[item.symbol] || [];
                    
                    // If no chart data but we have a price, create a simple chart
                    if (chartDataToUse.length === 0 && item.price > 0) {
                      const now = Date.now();
                      chartDataToUse = [];
                      for (let i = 0; i < 20; i++) {
                        chartDataToUse.push({
                          time: new Date(now - (20 - i) * 60000).toLocaleTimeString(),
                          price: item.price,
                          timestamp: now - (20 - i) * 60000
                        });
                      }
                    }
                    
                    // Determine if graph is red (same logic as list view: lastPrice < firstPrice)
                    if (chartDataToUse.length >= 2) {
                      const firstPrice = chartDataToUse[0].price;
                      const lastPrice = chartDataToUse[chartDataToUse.length - 1].price;
                      return lastPrice < firstPrice; // Red graph = downward trend
                    }
                    
                    // Fallback: check change percentages if no chart data
                    const change1h = item.change1h !== undefined && item.change1h !== null ? Number(item.change1h) : 0;
                    const change6h = item.change6h !== undefined && item.change6h !== null ? Number(item.change6h) : 0;
                    const change12h = item.change12h !== undefined && item.change12h !== null ? Number(item.change12h) : 0;
                    return (change1h < 0) || (change6h < 0) || (change12h < 0);
                  })
                  .sort((a, b) => {
                    // Sort by chart trend (most negative first)
                    let aChartData = a.chartData || chartDataCacheRef.current[a.symbol] || [];
                    let bChartData = b.chartData || chartDataCacheRef.current[b.symbol] || [];
                    
                    // Calculate trend percentage for sorting
                    let aTrend = 0;
                    let bTrend = 0;
                    
                    if (aChartData.length >= 2) {
                      const aFirst = aChartData[0].price;
                      const aLast = aChartData[aChartData.length - 1].price;
                      aTrend = aFirst > 0 ? ((aLast - aFirst) / aFirst) * 100 : 0;
                    } else {
                      // Fallback to change1h
                      aTrend = a.change1h !== undefined && a.change1h !== null ? Number(a.change1h) : 0;
                    }
                    
                    if (bChartData.length >= 2) {
                      const bFirst = bChartData[0].price;
                      const bLast = bChartData[bChartData.length - 1].price;
                      bTrend = bFirst > 0 ? ((bLast - bFirst) / bFirst) * 100 : 0;
                    } else {
                      // Fallback to change1h
                      bTrend = b.change1h !== undefined && b.change1h !== null ? Number(b.change1h) : 0;
                    }
                    
                    return aTrend - bTrend; // Most negative first
                  });
                  // Show ALL market down cryptos with red graphs (NO LIMIT)
                
                if (marketDownCryptos.length > 0) {
                  return (
                    <div className="market-down-section">
                      <div className="market-down-header">
                        <h5>Market Down</h5>
                        <p className="market-down-subtitle">
                        </p>
                      </div>
                      <div className="market-down-cards">
                        {marketDownCryptos.map((item) => {
                          const cryptoInfo = CRYPTO_NAMES[item.symbol] || { 
                            name: item.name || item.symbol, 
                            symbol: item.symbol.replace('USDT', '') 
                          };
                          
                          let chartDataToUse = item.chartData || chartDataCacheRef.current[item.symbol] || [];
                          
                          // If no chart data but we have a price, create a simple chart
                          if (chartDataToUse.length === 0 && item.price > 0) {
                            const now = Date.now();
                            chartDataToUse = [];
                            for (let i = 0; i < 20; i++) {
                              chartDataToUse.push({
                                time: new Date(now - (20 - i) * 60000).toLocaleTimeString(),
                                price: item.price,
                                timestamp: now - (20 - i) * 60000
                              });
                            }
                          }
                          
                          const hasChartData = chartDataToUse && chartDataToUse.length >= 2;
                          const chartColor = "#ef4444"; // Red for market down
                          
                          const iconConfig = getCryptoIconConfig(cryptoInfo.symbol);
                          
                          return (
                            <div key={item.symbol} className="market-down-card">
                              <div className="market-down-card-icon" style={{ background: iconConfig.bg }}>
                                {iconConfig.logo ? (
                                  <img 
                                    src={iconConfig.logo} 
                                    alt={cryptoInfo.symbol}
                                    className="crypto-logo"
                                    loading="lazy"
                                    onError={(e) => {
                                      // Hide image and show fallback
                                      e.target.style.display = 'none';
                                      const fallback = e.target.parentElement.querySelector('.crypto-icon-symbol');
                                      if (fallback) {
                                        fallback.style.display = 'flex';
                                      }
                                    }}
                                    onLoad={(e) => {
                                      // Hide fallback when image loads successfully
                                      const fallback = e.target.parentElement.querySelector('.crypto-icon-symbol');
                                      if (fallback) fallback.style.display = 'none';
                                    }}
                                  />
                                ) : null}
                                <span 
                                  className="crypto-icon-symbol" 
                                  style={{ 
                                    color: iconConfig.text,
                                    display: iconConfig.logo ? 'none' : 'flex'
                                  }}
                                >
                                  {cryptoInfo.symbol.length <= 3 ? cryptoInfo.symbol : cryptoInfo.symbol.charAt(0)}
                                </span>
                              </div>
                              <div className="market-down-card-content">
                                <div className="market-down-card-name">{cryptoInfo.name}</div>
                                <div className="market-down-card-price">
                                  ${item.price && item.price > 0 ? Number(item.price).toFixed(2) : 'N/A'}
                                </div>
                                <div className="market-down-card-change negative">
                                  <span className="change-arrow">▾</span> {
                                    item.change1h < 0 ? Math.abs(item.change1h).toFixed(2) :
                                    item.change6h < 0 ? Math.abs(item.change6h).toFixed(2) :
                                    Math.abs(item.change12h).toFixed(2)
                                  }%
                                </div>
                              </div>
                              <div className="market-down-card-chart">
                                {hasChartData ? (
                                  <ResponsiveContainer width="100%" height={50}>
                                    <LineChart 
                                      data={chartDataToUse} 
                                      margin={{ top: 5, right: 5, left: 5, bottom: 5 }}
                                    >
                                      <Line
                                        type="monotone"
                                        dataKey="price"
                                        stroke={chartColor}
                                        strokeWidth={2}
                                        dot={false}
                                        isAnimationActive={false}
                                        connectNulls={true}
                                      />
                                      <XAxis hide={true} dataKey="time" />
                                      <YAxis hide={true} domain={['auto', 'auto']} />
                                      <Tooltip content={() => null} />
                                    </LineChart>
                                  </ResponsiveContainer>
                                ) : (
                                  <div className="no-chart-data">—</div>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                }
                return null;
              })()}
              
              <div className="history-table-container">
              <table className="history-table">
                <thead>
                  <tr>
                    <th className="rank-col">#</th>
                    <th className="name-col">Cryptocurrency</th>
                    <th className="price-col">Price</th>
                    <th className="change-col">1h</th>
                    <th className="change-col">6h</th>
                    <th className="change-col">12h</th>
                    <th className="latency-col">Latency</th>
                    <th className="chart-col">Chart</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    // Show ALL instruments from config, even without data yet
                    const uniqueData = [];
                    const seenSymbols = new Set();
                    
                    // First, ensure all instruments from config are included (based on exchange)
                    const allConfigInstruments = getInstrumentsFromConfig(exchange);
                    allConfigInstruments.forEach(symbol => {
                      if (!seenSymbols.has(symbol)) {
                        seenSymbols.add(symbol);
                        const existingItem = historyData.find(item => item.symbol === symbol);
                        if (existingItem) {
                          uniqueData.push(existingItem);
                        } else {
                          // Create entry for instrument without data yet
                          const cryptoInfo = CRYPTO_NAMES[symbol] || { name: symbol.replace('USDT', ''), symbol: symbol.replace('USDT', '') };
                          uniqueData.push({
                            symbol,
                            name: cryptoInfo.name || symbol,
                            price: 0,
                            change1h: 0,
                            change6h: 0,
                            change12h: 0,
                            latency: 0,
                            lastUpdateTimestamp: null,
                            chartData: [],
                            hasData: false
                          });
                        }
                      }
                    });
                    
                    // For custom exchange, also include any instruments in historyData from subscription
                    // For OKX/Binance, only include instruments from their config
                    historyData.forEach(item => {
                      if (item.symbol && !seenSymbols.has(item.symbol)) {
                        if (exchange === 'custom') {
                          // Custom: include all instruments from subscription
                          seenSymbols.add(item.symbol);
                          uniqueData.push(item);
                        } else {
                          // OKX/Binance: only include if in config
                          if (allConfigInstruments.includes(item.symbol)) {
                            seenSymbols.add(item.symbol);
                            uniqueData.push(item);
                          }
                        }
                      }
                    });
                    
                    // Sort: instruments with data first (by price), then instruments without data (alphabetically)
                    uniqueData.sort((a, b) => {
                      const aHasData = a.price > 0 && a.hasData !== false;
                      const bHasData = b.price > 0 && b.hasData !== false;
                      
                      if (aHasData && !bHasData) return -1;
                      if (!aHasData && bHasData) return 1;
                      
                      if (aHasData && bHasData) {
                        return (b.price || 0) - (a.price || 0);
                      }
                      
                      // Both without data, sort alphabetically
                      return (a.symbol || '').localeCompare(b.symbol || '');
                    });
                    
                    return uniqueData.map((item, index) => {
                      const cryptoInfo = CRYPTO_NAMES[item.symbol] || { 
                        name: item.name || item.symbol, 
                        symbol: item.symbol.replace('USDT', '') 
                      };
                      
                      // Ensure we have valid change values
                      const change1h = item.change1h !== undefined && item.change1h !== null ? item.change1h : 0;
                      const change6h = item.change6h !== undefined && item.change6h !== null ? item.change6h : 0;
                      const change12h = item.change12h !== undefined && item.change12h !== null ? item.change12h : 0;
                      
                      return (
                        <tr key={`${item.symbol}-${index}`}>
                          <td className="rank-cell">{index + 1}</td>
                          <td className="symbol-name-cell">
                            <div className="crypto-name-wrapper">
                              <div className="crypto-name-with-logo">
                                {(() => {
                                  const iconConfig = getCryptoIconConfig(cryptoInfo.symbol);
                                  return (
                                    <>
                                      {iconConfig.logo ? (
                                        <img 
                                          src={iconConfig.logo} 
                                          alt={cryptoInfo.symbol}
                                          className="crypto-table-logo"
                                          onError={(e) => {
                                            // Hide image and show fallback
                                            e.target.style.display = 'none';
                                            const fallback = e.target.nextElementSibling;
                                            if (fallback) fallback.style.display = 'flex';
                                          }}
                                        />
                                      ) : null}
                                      <div 
                                        className="crypto-table-icon-fallback"
                                        style={{ 
                                          background: iconConfig.bg,
                                          display: iconConfig.logo ? 'none' : 'flex'
                                        }}
                                      >
                                        <span style={{ color: iconConfig.text }}>
                                          {cryptoInfo.symbol.length <= 3 ? cryptoInfo.symbol : cryptoInfo.symbol.charAt(0)}
                                        </span>
                                      </div>
                                    </>
                                  );
                                })()}
                                <div className="crypto-name-text">
                                  <span className="crypto-name">{cryptoInfo.name}</span>
                                  <span className="crypto-symbol">{cryptoInfo.symbol}</span>
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="price-cell">
                            {item.price > 0 ? `$${Number(item.price).toFixed(2)}` : 'N/A'}
                          </td>
                          <td className={`change-cell ${change1h >= 0 ? 'positive' : 'negative'}`}>
                            {item.price > 0 && change1h !== null && change1h !== undefined ? (
                              <>
                                {change1h >= 0 ? '▲' : '▼'} {Math.abs(change1h).toFixed(2)}%
                              </>
                            ) : (
                              'N/A'
                            )}
                          </td>
                          <td className={`change-cell ${change6h >= 0 ? 'positive' : 'negative'}`}>
                            {item.price > 0 && change6h !== null && change6h !== undefined ? (
                              <>
                                {change6h >= 0 ? '▲' : '▼'} {Math.abs(change6h).toFixed(2)}%
                              </>
                            ) : (
                              'N/A'
                            )}
                          </td>
                          <td className={`change-cell ${change12h >= 0 ? 'positive' : 'negative'}`}>
                            {item.price > 0 && change12h !== null && change12h !== undefined ? (
                              <>
                                {change12h >= 0 ? '▲' : '▼'} {Math.abs(change12h).toFixed(2)}%
                              </>
                            ) : (
                              'N/A'
                            )}
                          </td>
                          <td className="latency-cell">
                            {(() => {
                              let latency = item.latency;
                              if (item.lastUpdateTimestamp) {
                                latency = Math.max(0, Date.now() - item.lastUpdateTimestamp);
                              } else if (latency === null || latency === undefined) {
                                return 'N/A';
                              }
                              // Cap latency at 10s (10000ms)
                              if (latency > 10000) {
                                return '> 10s';
                              }
                              return `${Math.round(latency)}ms`;
                            })()}
                          </td>
                          <td className="graph-cell">
                            {(() => {
                              let chartDataToUse = item.chartData || chartDataCacheRef.current[item.symbol] || [];
                              
                              // If no chart data but we have a price, create a simple chart
                              if (chartDataToUse.length === 0 && item.price > 0) {
                                const now = Date.now();
                                chartDataToUse = [];
                                // Create chart with some variation based on price
                                const basePrice = item.price;
                                for (let i = 0; i < 20; i++) {
                                  const variation = (Math.random() - 0.5) * 0.02; // Small variation
                                  chartDataToUse.push({
                                    time: new Date(now - (20 - i) * 60000).toLocaleTimeString(),
                                    price: basePrice * (1 + variation),
                                    timestamp: now - (20 - i) * 60000
                                  });
                                }
                                // Cache it
                                chartDataCacheRef.current[item.symbol] = chartDataToUse;
                              }
                              
                              const hasChartData = chartDataToUse && chartDataToUse.length >= 2;
                              // Determine chart color based on overall trend
                              const firstPrice = chartDataToUse.length > 0 ? chartDataToUse[0].price : item.price;
                              const lastPrice = chartDataToUse.length > 0 ? chartDataToUse[chartDataToUse.length - 1].price : item.price;
                              const chartColor = lastPrice >= firstPrice ? "#10b981" : "#ef4444";
                              
                              if (hasChartData) {
                                return (
                                  <div style={{ width: '100%', height: '50px' }}>
                                    <ResponsiveContainer width="100%" height={50}>
                                      <LineChart 
                                        data={chartDataToUse} 
                                        margin={{ top: 5, right: 5, left: 5, bottom: 5 }}
                                      >
                                        <Line
                                          type="monotone"
                                          dataKey="price"
                                          stroke={chartColor}
                                          strokeWidth={2}
                                          dot={false}
                                          isAnimationActive={false}
                                          connectNulls={true}
                                        />
                                        <XAxis hide={true} dataKey="time" />
                                        <YAxis hide={true} domain={['auto', 'auto']} />
                                        <Tooltip content={() => null} />
                                      </LineChart>
                                    </ResponsiveContainer>
                                  </div>
                                );
                              }
                              // If no chart data, show a simple indicator
                              return <span className="no-graph">—</span>;
                            })()}
                          </td>
                        </tr>
                      );
                    });
                  })()}
                </tbody>
              </table>
            </div>
            </>
          )}
        </div>
      )}

      {activeTab === 'compare' && (
        <div className="comparison-container">
          <div className="comparison-header">
            <h4>Instrument Comparison</h4>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {comparisonLoading && (
              <span className="loading-indicator">⏳ Loading...</span>
            )}
              {comparisonData.length > 0 && (
                <div className="time-filter-buttons">
                  <button
                    className={`time-filter-btn ${timeFilter === '1h' ? 'active' : ''}`}
                    onClick={() => setTimeFilter('1h')}
                  >
                    1h
                  </button>
                  <button
                    className={`time-filter-btn ${timeFilter === '6h' ? 'active' : ''}`}
                    onClick={() => setTimeFilter('6h')}
                  >
                    6h
                  </button>
                  <button
                    className={`time-filter-btn ${timeFilter === '24h' ? 'active' : ''}`}
                    onClick={() => setTimeFilter('24h')}
                  >
                    24h
                  </button>
                </div>
              )}
            </div>
          </div>
          
          <div className="instrument-selector-wrapper">
            <div 
              className="instrument-selector-header"
              onClick={() => setIsInstrumentSelectorCollapsed(!isInstrumentSelectorCollapsed)}
            >
              <label style={{ display: 'block', margin: 0, fontWeight: 'bold', cursor: 'pointer', flex: 1 }}>
                Select Instruments to Compare:
              </label>
              <button 
                className="collapse-toggle-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  setIsInstrumentSelectorCollapsed(!isInstrumentSelectorCollapsed);
                }}
                aria-label={isInstrumentSelectorCollapsed ? 'Expand' : 'Collapse'}
              >
                <svg 
                  width="16" 
                  height="16" 
                  viewBox="0 0 16 16" 
                  fill="none" 
                  stroke="currentColor" 
                  strokeWidth="2"
                  style={{ 
                    transform: isInstrumentSelectorCollapsed ? 'rotate(-90deg)' : 'rotate(90deg)',
                    transition: 'transform 0.2s ease'
                  }}
                >
                  <path d="M6 12L10 8L6 4" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
            <div 
              className={`instrument-selector-content ${isInstrumentSelectorCollapsed ? 'collapsed' : ''}`}
            >
              <div className="instrument-selector">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '8px' }}>
                  {TRACKED_CRYPTO_SYMBOLS.map((sym) => {
                    const cryptoInfo = CRYPTO_NAMES[sym] || { name: sym, symbol: sym.replace('USDT', '') };
                    return (
                      <label key={sym} style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={selectedInstruments.includes(sym)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedInstruments([...selectedInstruments, sym]);
                            } else {
                              setSelectedInstruments(selectedInstruments.filter(s => s !== sym));
                            }
                          }}
                          style={{ marginRight: '8px', cursor: 'pointer' }}
                        />
                        <span>{cryptoInfo.name} {cryptoInfo.symbol}</span>
                      </label>
                    );
                  })}
                </div>
                <button
                  onClick={loadComparisonData}
                  style={{
                    marginTop: '15px',
                    padding: '10px 20px',
                    background: '#78176b',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: '600',
                    transition: 'all 0.2s'
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.background = '#5d0f52';
                    e.target.style.transform = 'translateY(-1px)';
                    e.target.style.boxShadow = '0 4px 8px rgba(120, 23, 107, 0.3)';
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.background = '#78176b';
                    e.target.style.transform = 'translateY(0)';
                    e.target.style.boxShadow = 'none';
                  }}
                >
                  Load Comparison
                </button>
              </div>
            </div>
          </div>

          {comparisonData.length > 0 && (
            <div className="chart-wrapper comparison-chart-minimal" style={{ marginTop: '20px' }}>
              <ResponsiveContainer width="100%" height={600}>
                <LineChart 
                  data={comparisonData} 
                  margin={{ top: 20, right: 30, left: 60, bottom: 100 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" opacity={0.4} />
                  <XAxis 
                    dataKey="time" 
                    tick={{ fontSize: 11, fill: '#6b7280' }}
                    stroke="#d1d5db"
                    strokeWidth={1}
                    interval={timeFilter === '1h' ? 'preserveStartEnd' : 'preserveStartEnd'}
                    angle={timeFilter === '1h' ? 0 : -45}
                    textAnchor={timeFilter === '1h' ? 'middle' : 'end'}
                    height={80}
                    style={{ fontSize: '11px' }}
                  />
                  <YAxis 
                    tick={{ fontSize: 11, fill: '#6b7280' }}
                    stroke="#d1d5db"
                    strokeWidth={1}
                    width={50}
                    label={{ 
                      value: '% Change', 
                      angle: -90, 
                      position: 'insideLeft', 
                      style: { fill: '#374151', fontSize: 12, fontWeight: 600 } 
                    }}
                    tickFormatter={(value) => `${value.toFixed(1)}%`}
                    domain={[
                      (dataMin) => {
                        const min = Math.min(0, dataMin || 0);
                        const padding = Math.max(0.5, Math.abs(min) * 0.1);
                        return Math.floor((min - padding) * 10) / 10;
                      },
                      (dataMax) => {
                        const max = Math.max(0, dataMax || 0);
                        const padding = Math.max(0.5, max * 0.1);
                        return Math.ceil((max + padding) * 10) / 10;
                      }
                    ]}
                  />
                  <Tooltip 
                    content={({ active, payload, label }) => {
                      if (active && payload && payload.length) {
                        // Find the full timestamp from comparisonData
                        const dataPoint = comparisonData.find(d => d.time === label);
                        const fullTime = dataPoint?.fullTime ? new Date(dataPoint.fullTime) : null;
                        const timeLabel = fullTime 
                          ? fullTime.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true })
                          : label;
                        
                        // Process payload directly from Recharts; each entry maps to the Line dataKey
                        const processedPayload = payload
                          .map(entry => {
                            const symbol = (entry.dataKey || entry.name || '').trim();
                            if (!symbol || !selectedInstruments.includes(symbol)) return null;

                            const value = typeof entry.value === 'number' ? entry.value : Number(entry.value) || 0;
                            const price =
                              entry.payload?.[`${symbol}_price`] ??
                              dataPoint?.[`${symbol}_price`] ??
                              0;

                            return {
                              symbol,
                              value,
                              price,
                              color: entry.color || '#3b82f6',
                            };
                          })
                          .filter(Boolean);
                        
                        return (
                          <div style={{
                            backgroundColor: 'rgba(255, 255, 255, 0.98)', 
                            border: '1px solid #3b82f6',
                            borderWidth: '2px',
                            borderRadius: '8px',
                            padding: '12px',
                            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                            minWidth: '200px'
                          }}>
                            <p style={{ 
                              margin: '0 0 10px 0', 
                              fontWeight: 600, 
                              color: '#111827', 
                              fontSize: '13px',
                              borderBottom: '1px solid #e5e7eb',
                              paddingBottom: '8px'
                            }}>
                              {timeLabel}
                            </p>
                            {processedPayload
                              .sort((a, b) => {
                                // Sort by symbol name for consistent display (alphabetical)
                                const aSymbol = CRYPTO_NAMES[a.symbol]?.symbol || a.symbol.replace('USDT', '');
                                const bSymbol = CRYPTO_NAMES[b.symbol]?.symbol || b.symbol.replace('USDT', '');
                                return aSymbol.localeCompare(bSymbol);
                              })
                              .map((item, index) => {
                                const cryptoInfo = CRYPTO_NAMES[item.symbol] || { 
                                  name: item.symbol, 
                                  symbol: item.symbol.replace('USDT', '') 
                                };
                                const displayName = cryptoInfo.symbol || item.symbol.replace('USDT', '');
                                const isPositive = item.value >= 0;
                                
                                return (
                                  <p key={`${item.symbol}-${index}`} style={{ 
                                    margin: '4px 0', 
                                    fontSize: '12px',
                                    color: '#374151',
                                    lineHeight: '1.5'
                                  }}>
                                    <span style={{ fontWeight: 600, color: item.color }}>
                                      {displayName}:
                                    </span>{' '}
                                    <span style={{ 
                                      color: isPositive ? '#10b981' : '#ef4444',
                                      fontWeight: 600
                                    }}>
                                      {isPositive ? '+' : ''}{item.value.toFixed(2)}%
                                    </span>
                                    {item.price > 0 && (
                                      <span style={{ color: '#6b7280', marginLeft: '8px', fontWeight: 500 }}>
                                        (${formatPrice(item.price)})
                                      </span>
                                    )}
                                  </p>
                                );
                              })}
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  {selectedInstruments.map((symbol, index) => {
                    // Assign consistent, distinct colors based on symbol - top 20 real-time assets
                    const colorMap = {
                      'BTCUSDT': '#3b82f6', // Blue for BTC
                      'ETHUSDT': '#10b981', // Green for ETH
                      'BNBUSDT': '#f97316', // Orange for BNB
                      'SOLUSDT': '#06b6d4', // Cyan
                      'XRPUSDT': '#78176b', // Purple for XRP
                      'ADAUSDT': '#ef4444', // Red for ADA
                      'DOGEUSDT': '#f59e0b', // Amber/Yellow
                      'MATICUSDT': '#ec4899', // Pink
                      'DOTUSDT': '#14b8a6', // Teal
                      'AVAXUSDT': '#84cc16', // Lime
                      'SHIBUSDT': '#f43f5e', // Rose
                      'TRXUSDT': '#a855f7', // Violet
                      'LINKUSDT': '#22c55e', // Emerald
                      'UNIUSDT': '#eab308', // Yellow
                      'ATOMUSDT': '#0ea5e9', // Sky
                      'LTCUSDT': '#6366f1', // Indigo
                      'ETCUSDT': '#fb923c', // Orange
                      'XLMUSDT': '#34d399', // Light Green
                      'ALGOUSDT': '#60a5fa', // Light Blue
                      'NEARUSDT': '#c084fc', // Fuchsia
                    };
                    
                    // Fallback colors for instruments not in map
                    const fallbackColors = [
                      '#3b82f6', '#10b981', '#f97316', '#78176b', '#ef4444',
                      '#06b6d4', '#f59e0b', '#ec4899', '#14b8a6', '#6366f1',
                      '#84cc16', '#f43f5e', '#a855f7', '#0ea5e9', '#22c55e',
                      '#eab308', '#fb923c', '#c084fc', '#60a5fa', '#34d399'
                    ];
                    
                    const color = colorMap[symbol] || fallbackColors[index % fallbackColors.length];
                    const cryptoInfo = CRYPTO_NAMES[symbol] || { symbol: symbol.replace('USDT', '') };
                    const displayName = cryptoInfo.symbol;
                    return (
                      <Line
                        key={symbol}
                        type="monotone"
                        dataKey={symbol}
                        stroke={color}
                        strokeWidth={2.5}
                        name={displayName}
                        dot={false}
                        activeDot={{ r: 5, fill: color, strokeWidth: 2, stroke: '#fff' }}
                        animationDuration={300}
                        connectNulls={true}
                      />
                    );
                  })}
                  <Legend 
                    wrapperStyle={{ 
                      paddingTop: '20px', 
                      fontSize: '13px',
                      textAlign: 'center',
                      display: 'flex',
                      justifyContent: 'center',
                      flexWrap: 'wrap',
                      gap: '15px'
                    }}
                    iconType="line"
                    iconSize={12}
                    formatter={(value) => <span style={{ color: '#374151', fontWeight: 500 }}>{value}</span>}
                  />
                  <ReferenceLine y={0} stroke="#9ca3af" strokeWidth={1} strokeDasharray="2 2" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {comparisonData.length === 0 && !comparisonLoading && (
            <div className="no-data">
              Select instruments and click "Load Comparison" to see the comparison chart.
            </div>
          )}
        </div>
      )}

      {activeTab === 'dashboard' && (
         <DashboardView historyData={historyData} globalStats={websocketData?.globalStats} exchange={exchange} showTopMovers={showTopMovers} />
      )}
    </div>
  );
}

 // Dashboard Component
 function DashboardView({ historyData, globalStats, showTopMovers = true }) {
  // Use useMemo to recalculate when historyData or globalStats changes (real-time updates)
  const calculateMarketMetrics = useMemo(() => {
    // Prefer real global stats when available
    if (globalStats) {
      return {
        totalMarketCap: globalStats.total_market_cap?.usd || 0,
        totalVolume: globalStats.total_volume_24h?.usd || 0,
        btcDominance: globalStats.market_cap_percentage?.btc || 0,
        ethDominance: globalStats.market_cap_percentage?.eth || 0,
        fearGreedIndex: 50, // Not provided by CoinGecko
        altcoinSeasonIndex: 50 // Placeholder
      };
    }

    if (!historyData || historyData.length === 0) {
      return {
        totalMarketCap: 0,
        totalVolume: 0,
        btcDominance: 0,
        ethDominance: 0,
        fearGreedIndex: 50,
        altcoinSeasonIndex: 50
      };
    }

    // Estimate market cap (price * estimated supply)
    // Using approximate circulating supplies for top 20 real-time assets
    const supplyEstimates = {
      'BTCUSDT': 19700000,
      'ETHUSDT': 120000000,
      'BNBUSDT': 150000000,
      'SOLUSDT': 450000000,
      'XRPUSDT': 55000000000,
      'ADAUSDT': 35000000000,
      'DOGEUSDT': 140000000000,
      'MATICUSDT': 10000000000,
      'DOTUSDT': 1200000000,
      'AVAXUSDT': 360000000,
      'SHIBUSDT': 589000000000000,
      'TRXUSDT': 90000000000,
      'LINKUSDT': 550000000,
      'UNIUSDT': 600000000,
      'ATOMUSDT': 300000000,
      'LTCUSDT': 74000000,
      'ETCUSDT': 140000000,
      'XLMUSDT': 28000000000,
      'ALGOUSDT': 8000000000,
      'NEARUSDT': 1000000000
    };

    let totalMarketCap = 0;
    let btcMarketCap = 0;
    let totalVolume = 0;

    historyData.forEach(item => {
      const supply = supplyEstimates[item.symbol] || 1000000000; // Default supply
      const marketCap = item.price * supply;
      totalMarketCap += marketCap;
      
      // Estimate volume (using price * random factor for demo)
      const estimatedVolume = marketCap * 0.05; // ~5% of market cap
      totalVolume += estimatedVolume;

      if (item.symbol === 'BTCUSDT') {
        btcMarketCap = marketCap;
      }
    });

    const btcDominance = totalMarketCap > 0 ? (btcMarketCap / totalMarketCap) * 100 : 0;

    // Calculate Fear & Greed Index (simplified: based on average price change)
    const avgChange = historyData.length > 0
      ? historyData.reduce((sum, item) => sum + (item.change1h || 0), 0) / historyData.length
      : 0;
    // Map change to 0-100 scale (negative = fear, positive = greed)
    const fearGreedIndex = Math.max(0, Math.min(100, 50 + (avgChange * 5)));

    // Altcoin Season Index (simplified: based on BTC dominance)
    // Lower BTC dominance = more altcoin season
    const altcoinSeasonIndex = Math.max(0, Math.min(100, 100 - btcDominance));

    return {
      totalMarketCap,
      totalVolume,
      btcDominance,
      ethDominance: 0,
      fearGreedIndex: Math.round(fearGreedIndex),
      altcoinSeasonIndex: Math.round(altcoinSeasonIndex)
    };
  }, [historyData, globalStats]);

  const metrics = calculateMarketMetrics;

  // Prepare data for charts - use real-time data from historyData
  const preparePriceHistoryData = useCallback((symbol, hours = 24) => {
    const item = historyData.find(d => d.symbol === symbol);
    if (!item || !item.chartData || item.chartData.length === 0) {
      // If no chart data but we have current price, create minimal real-time data
      if (item && item.price > 0) {
        const now = Date.now();
        const sampleData = [];
        for (let i = Math.min(hours, 10); i >= 0; i--) {
          const time = new Date(now - i * 3600000);
          sampleData.push({
            time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
            price: item.price,
            volume: item.price * 1000000 * 0.9
          });
        }
        return sampleData;
      }
      return [];
    }
    // Use real-time chart data - take last N points based on hours
    const pointsToTake = Math.min(hours * 2, item.chartData.length); // Approximate 2 points per hour
    return item.chartData.slice(-pointsToTake).map(point => ({
      ...point,
      volume: point.price * 1000000 * 0.9
    }));
  }, [historyData]);

  // Market cap history - use real-time data from historyData
  const marketCapHistory = useMemo(() => {
    if (historyData.length === 0) return [];
    
    // Collect all chart data points from all instruments and aggregate by time
    const timeMap = new Map();
    const supplyEstimates = {
      'BTCUSDT': 19700000, 'ETHUSDT': 120000000, 'BNBUSDT': 150000000, 'XRPUSDT': 55000000000,
      'ADAUSDT': 35000000000, 'SOLUSDT': 450000000, 'DOGEUSDT': 140000000000, 'MATICUSDT': 10000000000,
      'DOTUSDT': 1200000000, 'LTCUSDT': 74000000, 'AVAXUSDT': 360000000, 'SHIBUSDT': 589000000000000,
      'ATOMUSDT': 300000000, 'TRXUSDT': 90000000000, 'ETCUSDT': 140000000, 'LINKUSDT': 550000000,
      'UNIUSDT': 600000000, 'ALGOUSDT': 8000000000, 'VETUSDT': 72000000000, 'ICPUSDT': 450000000,
      'THETAUSDT': 1000000000, 'AXSUSDT': 130000000, 'SANDUSDT': 2000000000, 'EOSUSDT': 1100000000,
      'AAVEUSDT': 16000000, 'NEARUSDT': 1000000000, 'FILUSDT': 2000000000, 'XLMUSDT': 28000000000,
      'XTZUSDT': 900000000, 'USDCUSDT': 30000000000
    };
    
    historyData.forEach(item => {
      if (item.chartData && item.chartData.length > 0) {
        item.chartData.forEach(point => {
          // Use the time from chartData (already formatted with local timezone) as key
          const timeKey = point.time || new Date(point.timestamp).toLocaleString([], { 
            month: '2-digit', 
            day: '2-digit',
            hour: '2-digit', 
            minute: '2-digit',
            hour12: false 
          });
          const supply = supplyEstimates[item.symbol] || 1000000000;
          const marketCap = point.price * supply;
          
          if (!timeMap.has(timeKey)) {
            timeMap.set(timeKey, { time: timeKey, marketCap: 0, volume: 0, count: 0 });
          }
          const dataPoint = timeMap.get(timeKey);
          dataPoint.marketCap += marketCap;
          dataPoint.volume += marketCap * 0.05; // Estimate volume
          dataPoint.count += 1;
        });
      }
    });
    
    // Convert to array and sort by time, take last 30 points
    return Array.from(timeMap.values())
      .sort((a, b) => a.time.localeCompare(b.time))
      .slice(-30);
  }, [historyData]);

  // Top movers (24h) for gainers/losers cards
  const topGainers = useMemo(() => {
    return historyData
      .filter(item => item.price > 0 && item.hasData && item.change24h !== undefined)
      .sort((a, b) => (b.change24h || 0) - (a.change24h || 0))
      .slice(0, 5);
  }, [historyData]);

  const topLosers = useMemo(() => {
    return historyData
      .filter(item => item.price > 0 && item.hasData && item.change24h !== undefined)
      .sort((a, b) => (a.change24h || 0) - (b.change24h || 0))
      .slice(0, 5);
  }, [historyData]);

  // Top 5 coins for display cards (like CoinMarketCap)
  const top5Coins = useMemo(() => {
    return historyData
      .filter(item => item.price > 0 && item.hasData)
      .sort((a, b) => {
        // Sort by market cap if available, otherwise by price
        const aMarketCap = a.marketCap || (a.price * 1000000000);
        const bMarketCap = b.marketCap || (b.price * 1000000000);
        return bMarketCap - aMarketCap;
      })
      .slice(0, 5);
  }, [historyData]);

  // Prepare data for comparison chart - use real-time data
  return (
    <div className="dashboard-container">
      {/* Top Coins Section - Like CoinMarketCap */}
      {top5Coins.length > 0 && (
        <div className="dashboard-section">
          <h4 className="section-title">Top Coins</h4>
          <div className="top-coins-grid" style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', 
            gap: '12px',
            marginBottom: '20px'
          }}>
            {top5Coins.map((coin, index) => {
              const coinName = CRYPTO_NAMES[coin.symbol]?.name || coin.symbol.replace('USDT', '');
              const coinSymbol = CRYPTO_NAMES[coin.symbol]?.symbol || coin.symbol.replace('USDT', '');
              const change24h = coin.change24h || coin.change1h || 0;
              const isPositive = change24h >= 0;
              const sparklineData = coin.chartData?.slice(-24) || []; // Last 24 points for sparkline
              
              return (
                <div key={coin.symbol} className="top-coin-card" style={{
                  background: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px',
                  padding: '12px',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
                  minHeight: '140px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontWeight: '600', fontSize: '13px', color: '#374151' }}>
                      {coinName}
                    </span>
                    <span style={{ marginLeft: '8px', fontSize: '11px', color: '#6b7280' }}>
                      {coinSymbol}
                    </span>
                  </div>
                  <div style={{ fontSize: '18px', fontWeight: '700', color: '#111827', marginBottom: '4px' }}>
                    ${coin.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div style={{ 
                    fontSize: '12px', 
                    color: isPositive ? '#10b981' : '#ef4444',
                    marginBottom: '6px'
                  }}>
                    {isPositive ? '▲' : '▼'} {Math.abs(change24h).toFixed(2)}%
                  </div>
                  {sparklineData.length > 0 && (
                    <div style={{ height: '30px', width: '100%' }}>
                      <ResponsiveContainer width="100%" height={30}>
                        <LineChart data={sparklineData}>
                          <Line 
                            type="monotone" 
                            dataKey="price" 
                            stroke={isPositive ? '#10b981' : '#ef4444'} 
                            strokeWidth={2} 
                            dot={false}
                            isAnimationActive={false}
                          />
                          <XAxis hide dataKey="time" />
                          <YAxis hide />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Market Overview Section */}
      <div className="dashboard-section">
        <h4 className="section-title">Market Overview</h4>
        <div className="market-overview-grid">
          {/* Total Market Cap */}
          <div className="metric-card">
            <div className="metric-header">
              <span className="metric-label">Total Market Cap</span>
              {/* <span className="info-icon">ℹ️</span> */}
            </div>
            <div className="metric-value">
              {metrics.totalMarketCap >= 1e12 
                ? `$${(metrics.totalMarketCap / 1e12).toFixed(2)}T`
                : metrics.totalMarketCap >= 1e9
                ? `$${(metrics.totalMarketCap / 1e9).toFixed(2)}B`
                : metrics.totalMarketCap > 0
                ? `$${(metrics.totalMarketCap / 1e6).toFixed(2)}M`
                : '$0.00T'}
            </div>
            {globalStats ? (
              <div className="metric-change positive">
                <span>●</span> Live Data
              </div>
            ) : (
              <div className="metric-change positive">
                <span>▲</span> 2.5%
              </div>
            )}
            <div className="metric-sparkline">
              {marketCapHistory.length > 0 && (
                <ResponsiveContainer width="100%" height={30}>
                  <LineChart data={marketCapHistory}>
                    <Line type="monotone" dataKey="marketCap" stroke="#10b981" strokeWidth={2} dot={false} />
                    <XAxis hide dataKey="time" />
                    <YAxis hide />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* 24h Volume */}
          <div className="metric-card">
            <div className="metric-header">
              <span className="metric-label">24h Volume</span>
              {/* <span className="info-icon">ℹ️</span> */}
            </div>
            <div className="metric-value">
              {metrics.totalVolume >= 1e12 
                ? `$${(metrics.totalVolume / 1e12).toFixed(2)}T`
                : metrics.totalVolume >= 1e9
                ? `$${(metrics.totalVolume / 1e9).toFixed(2)}B`
                : metrics.totalVolume > 0
                ? `$${(metrics.totalVolume / 1e6).toFixed(2)}M`
                : '$0.00B'}
            </div>
            {globalStats ? (
              <div className="metric-change positive">
                <span>●</span> Live Data
              </div>
            ) : (
              <div className="metric-change positive">
                <span>▲</span> 5.2%
              </div>
            )}
            <div className="metric-sparkline">
              {marketCapHistory.length > 0 && (
                <ResponsiveContainer width="100%" height={30}>
                  <LineChart data={marketCapHistory}>
                    <Line type="monotone" dataKey="marketCap" stroke="#3b82f6" strokeWidth={2} dot={false} />
                    <XAxis hide dataKey="time" />
                    <YAxis hide />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Bitcoin Dominance */}
          <div className="metric-card">
            <div className="metric-header">
              <span className="metric-label">Bitcoin Dominance</span>
              {/* <span className="info-icon">ℹ️</span> */}
            </div>
            <div className="metric-value">
              {metrics.btcDominance.toFixed(1)}%
            </div>
            <div className="dominance-chart">
              <div className="dominance-bars">
                <div className="dominance-bar" style={{ width: `${metrics.btcDominance}%`, backgroundColor: '#f97316' }}></div>
                <div className="dominance-bar" style={{ width: `${metrics.ethDominance || 12.2}%`, backgroundColor: '#3b82f6' }}></div>
                <div className="dominance-bar" style={{ width: `${100 - metrics.btcDominance - (metrics.ethDominance || 12.2)}%`, backgroundColor: '#9ca3af' }}></div>
              </div>
              <div className="dominance-labels">
                <span style={{ color: '#f97316' }}>● BTC {metrics.btcDominance.toFixed(1)}%</span>
                <span style={{ color: '#3b82f6' }}>● ETH {(metrics.ethDominance || 12.2).toFixed(1)}%</span>
                <span style={{ color: '#9ca3af' }}>● Others {(100 - metrics.btcDominance - (metrics.ethDominance || 12.2)).toFixed(1)}%</span>
              </div>
            </div>
          </div>

          {/* Fear & Greed Index */}
          <div className="metric-card gauge-card">
            <div className="metric-header">
              <span className="metric-label">Fear & Greed Index</span>
              {/* <span className="info-icon">ℹ️</span> */}
            </div>
            <div className="fear-greed-gauge">
              <div className="gauge-container">
                <svg className="gauge-svg" viewBox="0 0 200 100">
                  <defs>
                    <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="#fbbf24" />
                      <stop offset="20%" stopColor="#f97316" />
                      <stop offset="40%" stopColor="#ef4444" />
                      <stop offset="60%" stopColor="#10b981" />
                      <stop offset="80%" stopColor="#059669" />
                      <stop offset="100%" stopColor="#047857" />
                    </linearGradient>
                  </defs>
                  {/* Semicircle arc */}
                  <path
                    d="M 20 80 A 80 80 0 0 1 180 80"
                    fill="none"
                    stroke="url(#gaugeGradient)"
                    strokeWidth="6"
                    strokeLinecap="round"
                  />
                  {/* Black dot pointer - positioned on the arc */}
                  {(() => {
                    const angle = (metrics.fearGreedIndex / 100) * Math.PI;
                    const centerX = 100;
                    const centerY = 80;
                    const radius = 80;
                    const dotX = centerX + Math.cos(Math.PI - angle) * radius;
                    const dotY = centerY - Math.sin(Math.PI - angle) * radius;
                    return (
                      <circle
                        cx={dotX}
                        cy={dotY}
                        r="5"
                        fill="#111827"
                        stroke="#ffffff"
                        strokeWidth="2"
                      />
                    );
                  })()}
                </svg>
                <div className="gauge-value">{metrics.fearGreedIndex}</div>
                <div className="gauge-labels">
                  <span className="gauge-label-left">Fear</span>
                  <span className="gauge-label-right">Greed</span>
                </div>
              </div>
            </div>
          </div>

          {/* Altcoin Season Index */}
          <div className="metric-card slider-card">
            <div className="metric-header">
              <span className="metric-label">Altcoin Season Index</span>
              {/* <span className="info-icon">ℹ️</span> */}
            </div>
            <div className="altcoin-season-value">{metrics.altcoinSeasonIndex}<span className="altcoin-season-denominator">/100</span></div>
            <div className="altcoin-season-slider">
              <div className="slider-track">
                <div 
                  className="slider-handle" 
                  style={{ left: `${metrics.altcoinSeasonIndex}%` }}
                ></div>
              </div>
              <div className="slider-labels">
                <span>Bitcoin Season</span>
                <span>Altcoin Season</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Top Movers (24h) */}
      {showTopMovers && (topGainers.length > 0 || topLosers.length > 0) && (
        <div className="dashboard-section" style={{ marginTop: '12px' }}>
          <h4 className="section-title">Top Movers (24h)</h4>
          <div className="market-overview-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px' }}>
            <div className="metric-card" style={{ borderRadius: '8px', padding: '16px', minHeight: '200px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div className="metric-header">
                <span className="metric-label" style={{ fontSize: '14px', fontWeight: '600' }}>Top Gainers</span>
              </div>
              <div className="metric-list" style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1 }}>
                {topGainers.map((coin) => {
                  const name = CRYPTO_NAMES[coin.symbol]?.name || coin.symbol.replace('USDT', '');
                  const pct = coin.change24h || 0;
                  return (
                    <div key={coin.symbol} className="metric-list-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                      <span className="metric-list-name" style={{ fontSize: '13px', color: '#374151' }}>{name}</span>
                      <span className="metric-list-value" style={{ color: '#10b981', fontSize: '13px', fontWeight: '600' }}>
                        +{pct.toFixed(2)}%
                      </span>
                    </div>
                  );
                })}
                {topGainers.length === 0 && <div className="metric-list-item" style={{ textAlign: 'center', color: '#9ca3af', padding: '20px 0' }}>No data</div>}
              </div>
            </div>

            <div className="metric-card" style={{ borderRadius: '8px', padding: '16px', minHeight: '200px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div className="metric-header">
                <span className="metric-label" style={{ fontSize: '14px', fontWeight: '600' }}>Top Losers</span>
              </div>
              <div className="metric-list" style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1 }}>
                {topLosers.map((coin) => {
                  const name = CRYPTO_NAMES[coin.symbol]?.name || coin.symbol.replace('USDT', '');
                  const pct = coin.change24h || 0;
                  return (
                    <div key={coin.symbol} className="metric-list-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                      <span className="metric-list-name" style={{ fontSize: '13px', color: '#374151' }}>{name}</span>
                      <span className="metric-list-value" style={{ color: '#ef4444', fontSize: '13px', fontWeight: '600' }}>
                        {pct.toFixed(2)}%
                      </span>
                    </div>
                  );
                })}
                {topLosers.length === 0 && <div className="metric-list-item" style={{ textAlign: 'center', color: '#9ca3af', padding: '20px 0' }}>No data</div>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Market Distribution & Analytics */}
      <div className="dashboard-section">
        <h4 className="section-title">Market Distribution & Analytics</h4>
        <div className="charts-grid-improved">
          {/* Market Cap Distribution Donut Chart */}
          {(() => {
            const supplyEstimates = {
              'BTCUSDT': 19700000,
              'ETHUSDT': 120000000,
              'BNBUSDT': 150000000,
              'XRPUSDT': 55000000000,
              'ADAUSDT': 35000000000,
              'SOLUSDT': 450000000,
              'DOGEUSDT': 140000000000,
              'MATICUSDT': 10000000000,
              'DOTUSDT': 1200000000,
              'LTCUSDT': 74000000,
              'AVAXUSDT': 360000000,
              'ATOMUSDT': 300000000,
              'LINKUSDT': 550000000,
              'UNIUSDT': 600000000,
              'AAVEUSDT': 16000000,
              'NEARUSDT': 1000000000,
              'FILUSDT': 2000000000
            };
            
            const marketCapData = historyData
              .filter(item => item.price > 0 && supplyEstimates[item.symbol])
              .map(item => ({
                name: CRYPTO_NAMES[item.symbol]?.symbol || item.symbol.replace('USDT', ''),
                value: item.price * supplyEstimates[item.symbol],
                fullName: CRYPTO_NAMES[item.symbol]?.name || item.symbol
              }))
              .sort((a, b) => b.value - a.value)
              .slice(0, 8);
            
            const COLORS = ['#3b82f6', '#f97316', '#10b981', '#ef4444', '#78176b', '#ec4899', '#f59e0b', '#06b6d4'];
            
            // If no data, show a message
            if (!marketCapData || marketCapData.length === 0) {
              return (
                <div className="chart-card-compact">
                  <div className="chart-header-compact">
                    <h5>Market Cap Distribution</h5>
                  </div>
                  <div style={{ 
                    height: '300px', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    color: '#9ca3af',
                    fontSize: '0.875rem'
                  }}>
                    No market data available. Please load data from the List or Compare tab first.
                  </div>
                </div>
              );
            }
            
            return (
              <div className="chart-card-compact">
                <div className="chart-header-compact">
                  <h5>Market Cap Distribution</h5>
                </div>
                <div style={{ width: '100%', height: '300px', minHeight: '300px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={marketCapData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percent }) => {
                          if (percent && percent > 0.05) {
                            return `${name} ${(percent * 100).toFixed(0)}%`;
                          }
                          return '';
                        }}
                        outerRadius={90}
                        innerRadius={50}
                        fill="#8884d8"
                        dataKey="value"
                        isAnimationActive={true}
                        animationBegin={0}
                        animationDuration={800}
                        paddingAngle={2}
                      >
                        {marketCapData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip 
                        formatter={(value, name, props) => [
                          `$${(value / 1e12).toFixed(2)}T`,
                          props.payload?.fullName || name
                        ]}
                        contentStyle={{ 
                          backgroundColor: 'rgba(255, 255, 255, 0.98)', 
                          border: '1px solid #e5e7eb',
                          borderRadius: '8px',
                          padding: '10px',
                          fontSize: '12px',
                          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
                        }}
                      />
                      <Legend 
                        verticalAlign="bottom" 
                        height={36}
                        formatter={(value, entry) => entry.payload?.fullName || value}
                        wrapperStyle={{ fontSize: '0.75rem' }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            );
          })()}

          {/* Price Change Heatmap */}
          <div className="chart-card-compact">
            <div className="chart-header-compact">
              <h5>Price Change Heatmap (24h)</h5>
            </div>
            <div className="heatmap-container">
              <div className="heatmap-grid">
                {historyData
                  .filter(item => item.price > 0)
                  .sort((a, b) => (b.change1h || 0) - (a.change1h || 0))
                  .slice(0, 20)
                  .map((item, index) => {
                    const change = item.change1h || 0;
                    const intensity = Math.min(Math.abs(change) / 10, 1);
                    const color = change >= 0 
                      ? `rgba(16, 185, 129, ${0.3 + intensity * 0.7})` 
                      : `rgba(239, 68, 68, ${0.3 + intensity * 0.7})`;
                    const cryptoInfo = CRYPTO_NAMES[item.symbol] || { 
                      name: item.name || item.symbol, 
                      symbol: item.symbol.replace('USDT', '') 
                    };
                    
                    return (
                      <div 
                        key={item.symbol} 
                        className="heatmap-cell"
                        style={{ 
                          backgroundColor: color,
                          borderColor: change >= 0 ? '#10b981' : '#ef4444'
                        }}
                        title={`${cryptoInfo.name}: ${change >= 0 ? '+' : ''}${change.toFixed(2)}%`}
                      >
                        <div className="heatmap-symbol">{cryptoInfo.symbol}</div>
                        <div className={`heatmap-change ${change >= 0 ? 'positive' : 'negative'}`}>
                          {change >= 0 ? '+' : ''}{change.toFixed(2)}%
                        </div>
                      </div>
                    );
                  })}
              </div>
              <div className="heatmap-legend">
                <div className="legend-item">
                  <span className="legend-color" style={{ backgroundColor: 'rgba(239, 68, 68, 0.8)' }}></span>
                  <span>Negative</span>
                </div>
                <div className="legend-item">
                  <span className="legend-color" style={{ backgroundColor: 'rgba(16, 185, 129, 0.8)' }}></span>
                  <span>Positive</span>
                </div>
              </div>
            </div>
          </div>

          {/* Volume vs Price */}
          <div className="chart-card-compact">
            <div className="chart-header-compact">
              <h5>Volume vs Price Correlation</h5>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={preparePriceHistoryData('BTCUSDT', 24)} margin={{ top: 10, right: 15, left: 5, bottom: 5 }}>
                <defs>
                  <linearGradient id="volumeGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.6}/>
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.2}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" opacity={0.15} />
                <XAxis 
                  dataKey="time" 
                  tick={{ fontSize: 10, fill: '#9ca3af' }} 
                  interval="preserveStartEnd"
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis 
                  yAxisId="left" 
                  tick={{ fontSize: 10, fill: '#9ca3af' }} 
                  axisLine={false}
                  tickLine={false}
                  width={55}
                  tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                  label={{ value: 'Price (USD)', angle: -90, position: 'insideLeft', style: { fontSize: '10px', fill: '#6b7280' } }} 
                />
                <YAxis 
                  yAxisId="right" 
                  orientation="right" 
                  tick={{ fontSize: 10, fill: '#9ca3af' }} 
                  axisLine={false}
                  tickLine={false}
                  width={55}
                  tickFormatter={(value) => `${(value / 1e9).toFixed(1)}B`}
                  label={{ value: 'Volume', angle: 90, position: 'insideRight', style: { fontSize: '10px', fill: '#6b7280' } }} 
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'rgba(255, 255, 255, 0.98)', 
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                    padding: '10px',
                    fontSize: '12px',
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
                  }}
                />
                <Bar yAxisId="right" dataKey="volume" fill="url(#volumeGradient)" name="Volume" radius={[2, 2, 0, 0]} />
                <Line yAxisId="left" type="monotone" dataKey="price" stroke="#ef4444" strokeWidth={2.5} name="Price" dot={false} activeDot={{ r: 5, fill: '#ef4444', strokeWidth: 2 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Market Analytics */}
      <div className="dashboard-section">
        <h4 className="section-title">Market Analytics</h4>
        <div className="market-analytics-grid">
          {/* Crypto Market Cap Chart */}
          <div className="chart-card-compact">
            <div className="chart-header-compact">
              <div>
                <h5>Crypto Market Cap</h5>
                <div className="chart-metrics">
                  <span className="metric-display">Market Cap: <strong>${(metrics.totalMarketCap / 1e12).toFixed(2)}T</strong></span>
                  <span className="metric-display">Volume: <strong>${(metrics.totalVolume / 1e9).toFixed(2)}B</strong></span>
                </div>
              </div>
              {/* <div className="chart-controls">
                <button className="time-btn">30d</button>
                <button className="time-btn">1y</button>
                <button className="time-btn">All</button>
              </div> */}
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={marketCapHistory} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                <defs>
                  <linearGradient id="volumeAreaGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3}/>
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.05}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" opacity={0.2} />
                <XAxis 
                  dataKey="time" 
                  tick={{ fontSize: 11, fill: '#9ca3af' }} 
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis 
                  yAxisId="left"
                  tick={{ fontSize: 11, fill: '#9ca3af' }} 
                  axisLine={false}
                  tickLine={false}
                  width={60}
                  tickFormatter={(value) => `$${(value / 1e12).toFixed(1)}T`}
                  label={{ value: 'Market Cap', angle: -90, position: 'insideLeft', style: { fontSize: '11px', fill: '#6b7280' } }}
                />
                <YAxis 
                  yAxisId="right"
                  orientation="right"
                  tick={{ fontSize: 11, fill: '#9ca3af' }} 
                  axisLine={false}
                  tickLine={false}
                  width={60}
                  tickFormatter={(value) => `$${(value / 1e9).toFixed(0)}B`}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'rgba(255, 255, 255, 0.98)', 
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                    padding: '10px',
                    fontSize: '12px',
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
                  }}
                />
                <Area 
                  yAxisId="right"
                  type="monotone" 
                  dataKey="volume" 
                  fill="url(#volumeAreaGradient)" 
                  stroke="none"
                  name="Volume"
                />
                <Line 
                  yAxisId="left"
                  type="monotone" 
                  dataKey="marketCap" 
                  stroke="#ef4444" 
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 5, fill: '#ef4444', strokeWidth: 2 }}
                  name="Market Cap"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Crypto ETFs Net Flow */}
          <div className="chart-card-compact">
            <div className="chart-header-compact">
              <div>
                <h5>Crypto ETFs Net Flow</h5>
                <div className="chart-metrics">
                  <span className="metric-display positive">+ $78,200,000</span>
                  <span className="metric-date">Nov 25, 2025</span>
                </div>
              </div>
              {/* <div className="chart-controls">
                <button className="time-btn active">30d</button>
                <button className="time-btn">1y</button>
                <button className="time-btn">All</button>
                <button className="time-btn">See More</button>
              </div> */}
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={(() => {
                // Generate sample ETF flow data with realistic patterns
                const dates = [];
                const now = Date.now();
                for (let i = 30; i >= 0; i--) {
                  const date = new Date(now - i * 24 * 60 * 60 * 1000);
                  const isPositive = Math.random() > 0.5;
                  const baseFlow = isPositive ? 400000000 : -400000000;
                  const variation = (Math.random() - 0.5) * 1200000000;
                  const netFlow = baseFlow + variation;
                  
                  dates.push({
                    date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                    positive: netFlow > 0 ? netFlow : 0,
                    negative: netFlow < 0 ? netFlow : 0,
                    netFlow: netFlow
                  });
                }
                return dates;
              })()} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" opacity={0.2} />
                <XAxis 
                  dataKey="date" 
                  tick={{ fontSize: 10, fill: '#9ca3af' }} 
                  axisLine={false}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis 
                  tick={{ fontSize: 11, fill: '#9ca3af' }} 
                  axisLine={false}
                  tickLine={false}
                  width={70}
                  tickFormatter={(value) => {
                    if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
                    if (value >= 1e6) return `$${(value / 1e6).toFixed(0)}M`;
                    return `$${(value / 1e3).toFixed(0)}K`;
                  }}
                  label={{ value: 'Net Flow (USD)', angle: -90, position: 'insideLeft', style: { fontSize: '11px', fill: '#6b7280' } }}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'rgba(255, 255, 255, 0.98)', 
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                    padding: '10px',
                    fontSize: '12px',
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
                  }}
                  formatter={(value) => {
                    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
                    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
                    return `$${(value / 1e3).toFixed(2)}K`;
                  }}
                />
                <ReferenceLine y={0} stroke="#9ca3af" strokeWidth={1.5} />
                <Bar dataKey="positive" fill="#3b82f6" name="Net Flow" radius={[2, 2, 0, 0]} />
                <Bar dataKey="negative" fill="#f97316" name="Net Flow" radius={[0, 0, 2, 2]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}

export default RealtimeStream;

