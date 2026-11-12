import { useCallback, useEffect, useState } from 'react'
import { ApiError, request } from './api.js'
import { authMode, currentToken, signIn, signOut, signUp } from './staffAuth.js'
import { AppShell, Button, Card, Field, inputCls, Notice, Spinner } from './ui.jsx'

const DEMO = {
  hospital: ['nurse.kath@bedalert.dev', 'admin.kath@bedalert.dev'],
  dispatch: ['dispatch.ashanti@bedalert.dev'],
  admin: ['admin@bedalert.dev'],
}

// Signs staff in, loads /v1/me, and hands children an authenticated `api`.
export default function StaffGate({ app, kind, children }) {
  const [state, setState] = useState({ status: 'loading' })

  const loadMe = useCallback(async () => {
    const token = await currentToken()
    if (!token) return setState({ status: 'signedOut' })
    try {
      const me = await request('/me', { token })
      setState({ status: 'ready', me })
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        await signOut()
        setState({ status: 'signedOut', error: 'Your session ended. Please sign in again.' })
      } else {
        setState({ status: 'error', error: e.message })
      }
    }
  }, [])

  useEffect(() => {
    loadMe()
  }, [loadMe])

  const api = useCallback(
    async (path, opts = {}) => {
      const token = await currentToken()
      try {
        return await request(path, { ...opts, token })
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          await signOut()
          setState({ status: 'signedOut', error: 'Your session ended. Please sign in again.' })
        }
        throw e
      }
    },
    [],
  )

  const doSignOut = async () => {
    await signOut()
    setState({ status: 'signedOut' })
  }

  if (state.status === 'loading')
    return (
      <AppShell app={app}>
        <div className="flex justify-center py-20 text-teal">
          <Spinner />
        </div>
      </AppShell>
    )

  if (state.status === 'signedOut' || state.status === 'error')
    return (
      <AppShell app={app}>
        <SignIn kind={kind} app={app} error={state.error} onDone={loadMe} />
      </AppShell>
    )

  return children({
    me: state.me,
    api,
    reloadMe: loadMe,
    signOutButton: (
      <>
        <span className="hidden md:inline text-slate-300">{state.me.email}</span>
        <Button variant="ghost" size="sm" className="!text-white hover:!bg-navy-light" onClick={doSignOut}>
          Sign out
        </Button>
      </>
    ),
  })
}

function SignIn({ kind, app, error, onDone }) {
  const [mode, setMode] = useState('in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(error ? { tone: 'warn', text: error } : null)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      if (mode === 'up') {
        const r = await signUp(email.trim(), password)
        if (r.needsConfirmation) {
          setMsg({ tone: 'ok', text: 'Account created. Check your email to confirm it, then sign in.' })
          setMode('in')
          return
        }
      } else {
        await signIn(email.trim(), password)
      }
      await onDone()
    } catch (err) {
      setMsg({ tone: 'error', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-md mx-auto mt-6">
      <Card className="p-6">
        <h1 className="font-display font-bold text-2xl text-navy">{mode === 'up' ? 'Create your staff account' : `Sign in to the ${app}`}</h1>
        <p className="text-sm text-slate-muted mt-1">For hospital staff, ambulance dispatchers and the BedAlert team.</p>
        <form onSubmit={submit} className="mt-5 space-y-4">
          <Field label="Work email">
            <input className={inputCls} type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          {authMode === 'supabase' && (
            <Field label="Password" hint={mode === 'up' ? 'At least 8 characters.' : undefined}>
              <input
                className={inputCls}
                type="password"
                required
                minLength={mode === 'up' ? 8 : undefined}
                autoComplete={mode === 'up' ? 'new-password' : 'current-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
          )}
          {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
          <Button type="submit" busy={busy} className="w-full" size="lg">
            {mode === 'up' ? 'Create account' : 'Sign in'}
          </Button>
        </form>
        {authMode === 'supabase' && (
          <button className="mt-4 text-sm text-teal font-semibold" onClick={() => setMode(mode === 'up' ? 'in' : 'up')}>
            {mode === 'up' ? 'I already have an account' : 'New here? Create an account'}
          </button>
        )}
        {authMode === 'dev' && (
          <Notice tone="warn" className="mt-5">
            <b>Development mode:</b> no password needed. Demo accounts:{' '}
            {DEMO[kind].map((d, i) => (
              <span key={d}>
                {i > 0 && ', '}
                <button className="underline font-mono-data" onClick={() => setEmail(d)}>
                  {d}
                </button>
              </span>
            ))}
          </Notice>
        )}
      </Card>
    </div>
  )
}
