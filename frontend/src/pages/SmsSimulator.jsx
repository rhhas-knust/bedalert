import { useState } from 'react'
import { api } from '../lib/api.js'

const PHONE = '+44 7700 900000'

export default function SmsSimulator() {
  const [log, setLog] = useState([
    { from: 'system', text: 'Dial *123# to start a BedAlert session.' },
  ])
  const [input, setInput] = useState('')
  const [started, setStarted] = useState(false)

  async function send(text) {
    setLog((l) => [...l, { from: 'user', text }])
    setInput('')
    try {
      const res = await api.sendSms({ phone: PHONE, text })
      setLog((l) => [...l, { from: 'system', text: res.reply }])
    } catch (err) {
      setLog((l) => [...l, { from: 'system', text: `Error: ${err.message}` }])
    }
  }

  function dial() {
    setStarted(true)
    send('*123#')
  }

  return (
    <div className="max-w-md mx-auto flex flex-col gap-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-navy">SMS / USSD simulator</h1>
        <p className="text-slate-muted text-sm mt-1">
          This is how BedAlert reaches areas with low or no internet — no smartphone or data required.
        </p>
      </div>

      <div className="bg-navy rounded-2xl p-4">
        <div className="bg-slate-bg rounded-xl h-96 flex flex-col overflow-hidden">
          <div className="bg-navy-dark text-white text-xs px-4 py-2 font-mono-data">{PHONE}</div>
          <div className="flex-1 overflow-y-auto px-3 py-3 flex flex-col gap-2">
            {log.map((m, i) => (
              <div
                key={i}
                className={`max-w-[80%] px-3 py-2 rounded-lg text-sm whitespace-pre-line ${
                  m.from === 'user'
                    ? 'self-end bg-teal text-white'
                    : 'self-start bg-white text-navy border border-slate-200'
                }`}
              >
                {m.text}
              </div>
            ))}
          </div>
          <div className="p-2 border-t border-slate-200 bg-white flex gap-2">
            {!started ? (
              <button
                onClick={dial}
                className="w-full py-2 rounded-md bg-teal text-white text-sm font-medium"
              >
                Dial *123#
              </button>
            ) : (
              <>
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && input && send(input)}
                  placeholder="Reply..."
                  className="flex-1 border border-slate-200 rounded-md px-3 py-2 text-sm"
                />
                <button
                  onClick={() => input && send(input)}
                  className="px-4 py-2 rounded-md bg-teal text-white text-sm font-medium"
                >
                  Send
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
