const BASE = '/api/v1/news'

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

export function listCategories() {
  return request('/categories')
}

export function getCategory(categorySlug) {
  return request(`/categories/${encodeURIComponent(categorySlug)}`)
}

export function getHotArticles(limit = 5) {
  return request(`/hot-articles?limit=${encodeURIComponent(String(limit))}`)
}

export function listArticles(params = {}) {
  const query = new URLSearchParams()
  if (params.category) query.set('category', params.category)
  if (params.limit) query.set('limit', String(params.limit))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return request(`/articles${suffix}`)
}

export function getArticle(articleId) {
  return request(`/articles/${encodeURIComponent(articleId)}`)
}

export function createArticle(payload) {
  return request('/articles', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}