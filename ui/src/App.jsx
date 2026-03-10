import { useState, useEffect, useRef } from 'react'
import Header from './components/Header'
import SummaryPanel from './components/SummaryPanel'
import LiveTranscript from './components/LiveTranscript'
import ChatBot from './components/ChatBot'
import LoginDialog from './components/LoginDialog'
import HistoryDashboard from './components/HistoryDashboard'
import { saveGuestMeeting, deleteGuestMeeting } from './utils/indexedDB'
import { loginWithGoogle } from './utils/auth'
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
  const [chatReady, setChatReady] = useState(false) // true as soon as first RAG chunk is indexed
  const [showLogin, setShowLogin] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [chatHistory, setChatHistory] = useState([]) // maintain Q&A state for guest storage
  const [chatDbHistory, setChatDbHistory] = useState([]) // chat history loaded from DB
  const authTokenRef = useRef(null)

  // ── #2 Fix: ref that always reflects latest meetingId for use inside closures ──
  const meetingIdRef = useRef(null)
  const statusRef = useRef('idle')

  useEffect(() => {
    statusRef.current = status
  }, [status])

  useEffect(() => {
    const handleUnload = () => {
      // If it's a guest AND they are not actively recording a live meeting
      if (!authTokenRef.current && statusRef.current !== 'recording') {
        if (meetingIdRef.current) deleteGuestMeeting(meetingIdRef.current)
        chromeApi.storage.local.remove('currentMeetingId')
      }
    }
    window.addEventListener('beforeunload', handleUnload)
    return () => window.removeEventListener('beforeunload', handleUnload)
  }, [])

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
        const authData = await chromeApi.storage.local.get('auth_token');
        if (authData.auth_token) {
          authTokenRef.current = authData.auth_token;
        }

        // Check if a recording is currently active — set by background.js.
        // If so, show the recording state and skip loading the old summary.
        const recData = await chromeApi.storage.local.get(['recording_active', 'activeMeetingId'])
        if (recData.recording_active && recData.activeMeetingId) {
          updateMeetingId(recData.activeMeetingId)
          setSummary(null)
          setStatus('recording')
          return  // Don't load any old summary during an active recording
        }

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
          if (!authTokenRef.current) setShowLogin(true)
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
        setChatHistory([])     // clear previous chat
        setChatDbHistory([])   // clear persisted history from previous meeting
        setChatReady(() => false)    // reset chat gating for new meeting
        setShowLogin(false)    // Hide login dialog from previous meetings
        setStatus(() => 'recording')
        chromeApi.storage.local.set({ currentMeetingId: msg.meeting_id })
      }

      if (msg.type === 'PARTIAL_TRANSCRIPT') {
        const newText = msg.text
        setLiveTranscript(prev => {
          if (prev.length > 0 && prev[prev.length - 1] === newText) return prev
          const nextState = [...prev, newText]

          // Save to IndexedDB if guest
          if (!authTokenRef.current && meetingIdRef.current) {
            const chunk = { speaker: "Unknown", text: newText, start_time: 0, end_time: 0 }
            saveGuestMeeting(meetingIdRef.current, { transcript_chunks: [{ speaker: "Guest", text: newText }] })
          }

          return nextState
        })
      }

      // RAG first chunk ready — enable chat during live meeting
      if (msg.type === 'CHAT_READY') {
        setChatReady(() => true)
        console.log("App.jsx: CHAT_READY received, unlocked chat")
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
        setStatus(() => 'processing')
        startPolling(id)
        setChatReady(() => true) // Ensure it's unlocked at the end
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

          // Load chat history from DB for authenticated users
          if (authTokenRef.current && authTokenRef.current !== 'LOGGED_IN') {
            try {
              const histRes = await fetchWithTimeout(
                `${API_BASE}/api/meetings/${id}`,
                { headers: { ...HEADERS, 'Authorization': `Bearer ${authTokenRef.current}` } }
              )
              if (histRes.ok) {
                const histData = await histRes.json()
                setChatDbHistory(histData.qa_history || [])
              }
            } catch (e) {
              console.warn('Could not load chat history from DB:', e.message)
            }
          } else {
            // Guest: save to IndexedDB and show login prompt
            saveGuestMeeting(id, { summary: data.summary })
            setShowLogin(true)
          }
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

    // Store the Q&A pair in App state for migration
    const qaPair = { question: question, answer: data.answer }
    setChatHistory(prev => {
      const nextState = [...prev, qaPair]
      // Save to IndexedDB if guest
      if (!authTokenRef.current && meetingIdRef.current) {
        saveGuestMeeting(meetingIdRef.current, { qa_history: nextState })
      }
      return nextState
    })

    return data.answer
  }

  // ── History handler ───────────────────────────────────────────────────────────
  async function handleOpenHistory() {
    if (!authTokenRef.current || authTokenRef.current === "LOGGED_IN") {
      // Since LOGGED_IN is a placeholder from LoginDialog, fetch the real one
      const authData = await chromeApi.storage.local.get('auth_token');
      if (authData.auth_token) {
        authTokenRef.current = authData.auth_token;
        setShowHistory(true);
        return;
      }
      // If absolutely no token, prompt login!
      try {
        const token = await loginWithGoogle();
        authTokenRef.current = token;
        setShowHistory(true);
      } catch (e) {
        console.warn("User cancelled login for history view.");
      }
    } else {
      setShowHistory(true);
    }
  }

  return (
    <div className="app">
      <Header meetingId={meetingId} onOpenHistory={handleOpenHistory} />
      <main className="app-main">
        <LiveTranscript lines={liveTranscript} status={status} />
        <SummaryPanel summary={summary} status={status} />
        {/* ── #7 Fix: pass status so ChatBot can show error message ── */}
        <ChatBot
          onSend={handleChat}
          disabled={!chatReady && status !== 'ready'}
          status={status}
          initialMessages={chatDbHistory}
        />

        {showLogin && (
          <LoginDialog
            onClose={(isLoggedIn) => {
              if (isLoggedIn) {
                // Instantly update local ref so it doesn't trigger again
                authTokenRef.current = "LOGGED_IN";
              }
              setShowLogin(false);
            }}
            currentMeetingData={{
              meeting_id: meetingIdRef.current,
              transcript_chunks: liveTranscript.map(t => ({ text: t })),
              summary: summary,
              qa_history: chatHistory
            }}
          />
        )}

        {showHistory && (
          <HistoryDashboard
            authToken={authTokenRef.current}
            onClose={() => setShowHistory(false)}
          />
        )}
      </main>
    </div>
  )
}
