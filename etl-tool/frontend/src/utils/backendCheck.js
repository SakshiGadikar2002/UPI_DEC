const BACKEND_URL = 'http://localhost:8000'

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

