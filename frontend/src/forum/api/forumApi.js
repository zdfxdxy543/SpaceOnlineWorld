const BASE = '/api/v1/forum'

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }
  return response.json()
}

export function getBoards() {
  return request('/boards')
}

export function getHotThreads(limit = 5) {
  return request(`/hot-threads?limit=${encodeURIComponent(String(limit))}`)
}

export function getBoardThreads(slug) {
  return request(`/boards/${encodeURIComponent(slug)}/threads`)
}

export function getThread(threadId) {
  return request(`/threads/${encodeURIComponent(threadId)}`)
}

export function getUser(userId) {
  return request(`/users/${encodeURIComponent(userId)}`)
}

export function createThread(payload) {
  return request('/threads', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function replyThread(threadId, payload) {
  return request(`/threads/${encodeURIComponent(threadId)}/replies`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}