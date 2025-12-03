/**
 * WebSocket client for real-time data updates
 */
class RealtimeWebSocket {
  constructor(url = null) {
    // Use current host/port if no URL provided (works when served from same port)
    if (!url) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      url = `${protocol}//${host}/api/realtime`
    }
    this.url = url
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 1000
    this.listeners = new Map()
    this.isConnecting = false
  }

  connect() {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      console.log('WebSocket already connecting or connected')
      return
    }

    this.isConnecting = true
    console.log(`Connecting to WebSocket: ${this.url}`)

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        console.log('✅ WebSocket connected successfully')
        this.isConnecting = false
        this.reconnectAttempts = 0
        this.emit('connected')
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('📨 Received WebSocket message:', data.type || 'data', data)
          
          // Handle ping messages (keep-alive)
          if (data.type === 'ping') {
            // Optionally send pong back
            return
          }
          
          // Emit message event for data messages
          if (data.type !== 'connected' && data.type !== 'ping') {
            this.emit('message', data)
          } else if (data.type === 'connected') {
            // Already handled by connected event
          }
        } catch (e) {
          console.error('Error parsing WebSocket message:', e, event.data)
        }
      }

      this.ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error)
        this.emit('error', error)
        this.isConnecting = false
      }

      this.ws.onclose = (event) => {
        console.log(`WebSocket disconnected. Code: ${event.code}, Reason: ${event.reason || 'Unknown'}`)
        this.isConnecting = false
        this.emit('disconnected')

        // Only attempt to reconnect if it wasn't a manual close
        if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++
          const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
          console.log(`Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
          setTimeout(() => this.connect(), delay)
        } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
          console.error('Max reconnection attempts reached')
          this.emit('reconnect_failed')
        }
      }
    } catch (error) {
      console.error('Error creating WebSocket:', error)
      this.isConnecting = false
      this.emit('error', error)
    }
  }

  disconnect() {
    console.log('Disconnecting WebSocket...')
    this.reconnectAttempts = this.maxReconnectAttempts // Prevent reconnection
    if (this.ws) {
      this.ws.close(1000, 'Manual disconnect') // Normal closure
      this.ws = null
    }
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, [])
    }
    this.listeners.get(event).push(callback)
  }

  off(event, callback) {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event)
      const index = callbacks.indexOf(callback)
      if (index > -1) {
        callbacks.splice(index, 1)
      }
    }
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => {
        try {
          callback(data)
        } catch (e) {
          console.error('Error in event listener:', e)
        }
      })
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    } else {
      console.warn('WebSocket is not open')
    }
  }

  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN
  }
}

// Export singleton instance
let instance = null

export function getRealtimeWebSocket() {
  if (!instance) {
    instance = new RealtimeWebSocket()
  }
  return instance
}

export default RealtimeWebSocket

