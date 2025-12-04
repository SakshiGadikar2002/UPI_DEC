// Use relative URL - works when frontend is served from same port as backend
const BACKEND_URL = ''

export const checkBackendHealth = async () => {
  try {
    const response = await fetch(`${BACKEND_URL}/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    return response.ok
  } catch (error) {
    return false
  }
}

