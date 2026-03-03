import { useState, useEffect, useRef } from 'react'
import Header from './components/Header'
import SummaryPanel from './components/SummaryPanel'
import LiveTranscript from './components/LiveTranscript'
import ChatBot from './components/ChatBot'
import './App.css'

const API_BASE = 'https://debroah-prehazard-candance.ngrok-free.dev'
const HEADERS = { 'ngrok-skip-browser-warning': 'true' }
const MAX_POLL_RETRIES = 60   // 60 × 2 s = 2 minutes max

// ── #5 Fix: guard against missing chrome API in dev mode ─────────────────────
const chromeApi = typeof chrome !== 'undefined' ? chrome : {
  storage: { local: { get: async () => ({}), set: async () => { } } },
  runtime: { onMessage: { addListener: () => { }, removeListener: () => { } } },
}

// ── Fetch with AbortController timeout ───────────────────────────────────────
// Prevents fetch from hanging forever if backend/ngrok goes silent.
async function fetchWithTimeout(url, options = {}, timeoutMs = 8000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(url, { ...options, signal: controller.signal })
    clearTimeout(timer)
    return res
  } catch (e) {
    clearTimeout(timer)
    if (e.name === 'AbortError') throw new Error(`Request timed out after ${timeoutMs}ms`)
    throw e
  }
}

export default function App() {
  const [meetingId, setMeetingId] = useState(null)
  const [summary, setSummary] = useState(null)   // null=loading, false=error, obj=ready
  const [status, setStatus] = useState('idle') // idle|recording|processing|ready|error
  const [liveTranscript, setLiveTranscript] = useState([]) // real-time transcript lines

  // ── #2 Fix: ref that always reflects latest meetingId for use inside closures ──
  const meetingIdRef = useRef(null)
  // ── #3 & #4 Fix: single interval ref cleared on new meeting / remount ────────
  const pollingRef = useRef(null)
  const pollingStarted = useRef(false)
  const pollRetryCount = useRef(0)

  function updateMeetingId(id) {
    setMeetingId(id)
    meetingIdRef.current = id
  }

  // ── #3 Fix: always stop existing polling before starting a new one ────────────
  function stopPolling() {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    pollingStarted.current = false
    pollRetryCount.current = 0
  }

  // ── Bootstrap: restore from local storage ────────────────────────────────────
  useEffect(() => {
    async function bootstrap() {
      try {
        const stored = await chromeApi.storage.local.get('currentMeetingId')
        if (!stored.currentMeetingId) return

        updateMeetingId(stored.currentMeetingId)
        setStatus('processing')

        const res = await fetchWithTimeout(
          `${API_BASE}/meeting/${stored.currentMeetingId}/summary`,
          { headers: HEADERS }
        )
        const data = await res.json()

        if (data.status === 'READY') {
          setSummary(data.summary)
          setStatus('ready')
        } else if (data.status === 'PROCESSING') {
          // ── #4 Fix: only start polling if not already running ─────────────────
          if (!pollingStarted.current) startPolling(stored.currentMeetingId)
        }
      } catch (e) {
        console.warn('Bootstrap failed', e)
      }
    }
    bootstrap()

    // Cleanup polling on unmount
    return () => stopPolling()
  }, [])

  // ── Chrome runtime messages ───────────────────────────────────────────────────
  useEffect(() => {
    function onMessage(msg) {
      if (msg.type === 'MEETING_STARTED') {
        // ── #3 Fix: kill any running polling before starting fresh ────────────
        stopPolling()

        updateMeetingId(msg.meeting_id)
        setSummary(null)
        setLiveTranscript([])  // clear previous transcript
        setStatus('recording')
        chromeApi.storage.local.set({ currentMeetingId: msg.meeting_id })
      }

      if (msg.type === 'PARTIAL_TRANSCRIPT') {
        setLiveTranscript(prev => {
          if (prev.length > 0 && prev[prev.length - 1] === msg.text) return prev
          return [...prev, msg.text]
        })
      }

      if (msg.type === 'MEETING_ENDED') {
        if (pollingStarted.current) return

        // ── #2 Fix: use ref (always fresh) instead of stale closure state ─────
        const id = msg.meeting_id || meetingIdRef.current
        if (!id) {
          console.warn('MEETING_ENDED received but no meeting_id available')
          return
        }
        updateMeetingId(id)
        setStatus('processing')
        startPolling(id)
      }
    }

    chromeApi.runtime.onMessage.addListener(onMessage)
    return () => chromeApi.runtime.onMessage.removeListener(onMessage)
  }, [])  // empty deps — safe because we use refs for fresh values

  // ── Polling with retry limit ──────────────────────────────────────────────────
  function startPolling(id) {
    if (pollingStarted.current) return   // ── #4 Fix: prevent duplicate intervals
    pollingStarted.current = true
    pollRetryCount.current = 0

    pollingRef.current = setInterval(async () => {
      // ── #6 Fix: enforce max retry limit ──────────────────────────────────────
      pollRetryCount.current += 1
      if (pollRetryCount.current > MAX_POLL_RETRIES) {
        stopPolling()
        setSummary(false)
        setStatus('error')
        console.warn('Polling timed out after max retries')
        return
      }

      try {
        const res = await fetchWithTimeout(`${API_BASE}/meeting/${id}/summary`, { headers: HEADERS })
        const data = await res.json()

        if (data.status === 'READY') {
          stopPolling()
          setSummary(data.summary)
          setStatus('ready')
        }
        if (data.status === 'NOT_FOUND') {
          stopPolling()
          setSummary(false)
          setStatus('error')
        }
      } catch (e) {
        // Network error — log and continue polling (will hit retry limit eventually)
        console.warn(`Poll attempt ${pollRetryCount.current} failed:`, e.message)
      }
    }, 2000)
  }

  // ── Chat handler ──────────────────────────────────────────────────────────────
  async function handleChat(question) {
    const res = await fetchWithTimeout(`${API_BASE}/chat/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...HEADERS },
      body: JSON.stringify({ meeting_id: meetingIdRef.current, question }),
    }, 30000)  // 30s — LLM can be slow on first query
    const data = await res.json()
    return data.answer
  }

  return (
    <div className="app">
      <Header meetingId={meetingId} />
      <main className="app-main">
        <LiveTranscript lines={liveTranscript} status={status} />
        <SummaryPanel summary={summary} status={status} />
        {/* ── #7 Fix: pass status so ChatBot can show error message ── */}
        <ChatBot
          onSend={handleChat}
          disabled={status !== 'ready'}
          status={status}
        />
      </main>
    </div>
  )
}
