/**
 * SSE 客户端：POST /api/chat 流式接收事件。
 * 用 fetch + ReadableStream（EventSource 只支持 GET）。
 */
import { useVaultStore } from '../stores/vault'

export async function streamChat({ messages, repo, maxIterations = 8, onEvent, signal }) {
  const url = '/api/chat' + (repo ? `?repo=${encodeURIComponent(repo)}` : '')
  const vault = useVaultStore()
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...vault.authHeaders(),
    },
    body: JSON.stringify({ messages, max_iterations: maxIterations }),
    signal,
  })
  if (!resp.ok) {
    const txt = await resp.text()
    throw new Error(`chat ${resp.status}: ${txt}`)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, idx).replace(/\r$/, '')
      buffer = buffer.slice(idx + 1)
      if (line === '') {
        currentEvent = null
        continue
      }
      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        const raw = line.slice(5).trim()
        let data
        try {
          data = JSON.parse(raw)
        } catch {
          data = raw
        }
        onEvent?.({ type: currentEvent || 'message', data })
      }
    }
  }
}
