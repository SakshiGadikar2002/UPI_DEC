export const OKX_CONFIG = {
  WS_URL: 'wss://ws.okx.com:8443/ws/v5/public',
  INSTRUMENTS: {
    ALL: 'ALL',
    BTC_USDT: 'BTC-USDT',
    ETH_USDT: 'ETH-USDT',
    BNB_USDT: 'BNB-USDT',
    SOL_USDT: 'SOL-USDT',
    XRP_USDT: 'XRP-USDT',
    ADA_USDT: 'ADA-USDT',
    DOGE_USDT: 'DOGE-USDT',
    MATIC_USDT: 'MATIC-USDT',
    DOT_USDT: 'DOT-USDT',
    AVAX_USDT: 'AVAX-USDT',
    SHIB_USDT: 'SHIB-USDT',
    TRX_USDT: 'TRX-USDT',
    LINK_USDT: 'LINK-USDT',
    UNI_USDT: 'UNI-USDT',
    ATOM_USDT: 'ATOM-USDT',
    LTC_USDT: 'LTC-USDT',
    ETC_USDT: 'ETC-USDT',
    XLM_USDT: 'XLM-USDT',
    ALGO_USDT: 'ALGO-USDT',
    NEAR_USDT: 'NEAR-USDT'
  },
  createSubscribeMessage: (channel, instId) => {
    if (instId === 'ALL') {
      // Subscribe to top 20 most liquid real-time instruments
      const allInstruments = [
        'BTC-USDT', 'ETH-USDT', 'BNB-USDT', 'SOL-USDT', 'XRP-USDT',
        'ADA-USDT', 'DOGE-USDT', 'MATIC-USDT', 'DOT-USDT', 'AVAX-USDT',
        'SHIB-USDT', 'TRX-USDT', 'LINK-USDT', 'UNI-USDT', 'ATOM-USDT',
        'LTC-USDT', 'ETC-USDT', 'XLM-USDT', 'ALGO-USDT', 'NEAR-USDT'
      ]
      return {
        op: 'subscribe',
        args: allInstruments.map(id => ({ channel, instId: id }))
      }
    }
    return {
      op: 'subscribe',
      args: [{ channel, instId }]
    }
  }
}

export const BINANCE_CONFIG = {
  WS_URL: 'wss://stream.binance.com:9443/ws/',
  SYMBOLS: {
    ALL: 'ALL',
    BTC_USDT: 'btcusdt',
    ETH_USDT: 'ethusdt',
    BNB_USDT: 'bnbusdt',
    SOL_USDT: 'solusdt',
    XRP_USDT: 'xrpusdt',
    ADA_USDT: 'adausdt',
    DOGE_USDT: 'dogeusdt',
    MATIC_USDT: 'maticusdt',
    DOT_USDT: 'dotusdt',
    AVAX_USDT: 'avaxusdt',
    SHIB_USDT: 'shibusdt',
    TRX_USDT: 'trxusdt',
    LINK_USDT: 'linkusdt',
    UNI_USDT: 'uniusdt',
    ATOM_USDT: 'atomusdt',
    LTC_USDT: 'ltcusdt',
    ETC_USDT: 'etcusdt',
    XLM_USDT: 'xlmusdt',
    ALGO_USDT: 'algousdt',
    NEAR_USDT: 'nearusdt'
  },
  createStreamName: (symbol, streamType) => {
    if (symbol === 'ALL') {
      // Create combined stream for top 20 most liquid real-time symbols
      const allSymbols = [
        'btcusdt', 'ethusdt', 'bnbusdt', 'solusdt', 'xrpusdt',
        'adausdt', 'dogeusdt', 'maticusdt', 'dotusdt', 'avaxusdt',
        'shibusdt', 'trxusdt', 'linkusdt', 'uniusdt', 'atomusdt',
        'ltcusdt', 'etcusdt', 'xlmusdt', 'algousdt', 'nearusdt'
      ]
      const streams = allSymbols.map(s => `${s}@${streamType}`).join('/')
      return streams
    }
    // Ensure symbol is lowercase for Binance
    const lowerSymbol = symbol.toLowerCase()
    return `${lowerSymbol}@${streamType}`
  }
}

