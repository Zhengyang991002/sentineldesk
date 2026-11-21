import { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import * as api from '../api/client.js'
import geminiLogo from '../../assets/gemini_logo.webp'
import { localReply } from '../mocks/chatFallback.js'
import Icon from './Icon.jsx'

const GREETING = { role: 'bot', text: 'Hi! Ask me anything about the current ticket.' }

// Gemini assistant. Collapsed it is a floating button whose input slides out on hover; sending a
// message opens the conversation as a panel docked to the right edge.
//
//   result:  the analysis sent to /chat as context (null before the first analysis)
//   current: { subject, body } of the ticket in the form, shown in the panel header
export default function ChatWidget({ result, current }) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [messages, setMessages] = useState([GREETING])
  const conversationId = useRef(0) // bumped by "new chat" so a late reply is dropped
  const inputRef = useRef(null)
  const endRef = useRef(null)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  // The panel is visibility:hidden while closed, so focus after it has transitioned in.
  useEffect(() => {
    if (!open) return
    const t = setTimeout(() => inputRef.current?.focus(), 60)
    return () => clearTimeout(t)
  }, [open])

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, typing, open])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (e) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open])

  // Keep the panel above the page footer (--footer-h is read by .chat-panel).
  useEffect(() => {
    const footer = document.querySelector('.footer')
    if (!footer) return
    const update = () => document.documentElement.style.setProperty('--footer-h', `${footer.offsetHeight}px`)
    update()
    const observer = new ResizeObserver(update)
    observer.observe(footer)
    return () => observer.disconnect()
  }, [])

  // Lets the stylesheet make room for the docked panel.
  useEffect(() => {
    document.documentElement.classList.toggle('chat-docked', open)
    return () => document.documentElement.classList.remove('chat-docked')
  }, [open])

  function newChat() {
    conversationId.current += 1
    setMessages([GREETING])
    setInput('')
    setTyping(false)
    inputRef.current?.focus()
  }

  async function send(e) {
    e.preventDefault()
    const question = input.trim()
    if (!question || typing) return
    setOpen(true)
    // The greeting is not part of the conversation; the backend keeps only the latest turns.
    const history = messages.slice(1).map(({ role, text }) => ({ role, text }))
    const id = conversationId.current
    setMessages((m) => [...m, { role: 'user', text: question }])
    setInput('')
    setTyping(true)

    let reply
    try {
      const data = await api.chat({ message: question, history, ticket: result })
      reply = { role: 'bot', text: data.reply }
    } catch {
      // Gemini is not configured or unreachable: answer locally (MOCK, see mocks/chatFallback.js).
      reply = { role: 'bot', text: localReply(question, result), fallback: true }
    }
    if (!mounted.current || id !== conversationId.current) return
    setMessages((m) => [...m, reply])
    setTyping(false)
  }

  return (
    <>
      <section className={`chat-panel ${open ? 'open' : ''}`} role="dialog" aria-label="Ask Gemini" aria-hidden={!open}>
        <header className="chat-head">
          <img src={geminiLogo} alt="" width="16" height="16" />
          <span className="chat-title">Ask Gemini</span>
          {current ? (
            <span className="chat-ticket" title={current.body}>{current.subject || current.body}</span>
          ) : (
            <span className="chat-spacer" />
          )}
          <button type="button" className="icon-btn" onClick={newChat} aria-label="New chat" title="New chat" tabIndex={open ? 0 : -1}>
            <Icon name="newChat" size={18} />
          </button>
          <button type="button" className="icon-btn" onClick={() => setOpen(false)} aria-label="Close chat" tabIndex={open ? 0 : -1}>
            <Icon name="close" size={18} />
          </button>
        </header>

        <div className="chat-log" aria-live="polite">
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.role === 'bot' ? (
                <Markdown components={{ a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}>
                  {m.text}
                </Markdown>
              ) : (
                m.text
              )}
              {m.fallback && <div className="msg-note">Gemini unavailable · local reply</div>}
            </div>
          ))}
          {typing && (
            <div className="msg bot typing" aria-label="Gemini is typing">
              <span /><span /><span />
            </div>
          )}
          <div ref={endRef} />
        </div>

        <form className="chat-form" onSubmit={send}>
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about this ticket…"
            aria-label="Message"
            autoComplete="off"
            tabIndex={open ? 0 : -1}
          />
          <button type="submit" className="icon-btn" disabled={!input.trim() || typing} aria-label="Send" tabIndex={open ? 0 : -1}>
            <Icon name="send" />
          </button>
        </form>
      </section>

      <div className={`chat ${open ? 'hidden' : ''} ${input.trim() ? 'has-text' : ''}`}>
        <form className="chat-pill" onSubmit={send}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about this ticket…"
            aria-label="Ask Gemini"
            autoComplete="off"
            tabIndex={open ? -1 : 0}
          />
        </form>
        <button
          type="button"
          className="fab"
          onClick={() => setOpen(true)}
          aria-label="Open Gemini chat"
          title="Ask Gemini"
          tabIndex={open ? -1 : 0}
        >
          <img src={geminiLogo} alt="" width="26" height="26" />
        </button>
      </div>
    </>
  )
}
