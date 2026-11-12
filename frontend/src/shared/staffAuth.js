// Staff sign-in for the hospital, dispatch and admin apps.
//
// Production: Supabase Auth (email + password). Set VITE_SUPABASE_URL and
// VITE_SUPABASE_ANON_KEY (the project's publishable key) on Vercel.
// Development: without those, the API's dev-only /v1/dev/staff-token route
// signs in any email, so the demo accounts from scripts/seed_dev work.
import { request } from './api.js'

const SUPA_URL = import.meta.env.VITE_SUPABASE_URL
const SUPA_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY
export const authMode = SUPA_URL && SUPA_KEY ? 'supabase' : 'dev'

const DEV_KEY = 'bedalert.staff.dev'
let devMemory = null // fallback when localStorage is unavailable
let supabasePromise = null
function supabase() {
  if (!supabasePromise) {
    supabasePromise = import('@supabase/supabase-js').then(({ createClient }) => createClient(SUPA_URL, SUPA_KEY))
  }
  return supabasePromise
}

function readDev() {
  try {
    const s = JSON.parse(localStorage.getItem(DEV_KEY) || 'null')
    return s && s.exp > Date.now() ? s : null
  } catch {
    return null
  }
}

export async function getToken() {
  if (authMode === 'supabase') {
    const { data } = await (await supabase()).auth.getSession()
    return data.session?.access_token || null
  }
  return readDev()?.token || null
}

export async function signIn(email, password) {
  if (authMode === 'supabase') {
    const { error } = await (await supabase()).auth.signInWithPassword({ email, password })
    if (error) throw new Error(error.message)
    return
  }
  const res = await request('/dev/staff-token', { method: 'POST', body: { email } })
  try {
    localStorage.setItem(DEV_KEY, JSON.stringify({ token: res.access_token, email, exp: Date.now() + 55 * 60 * 1000 }))
  } catch {
    /* private mode: token lives only for this page */
  }
  devMemory = res.access_token
}

export async function signUp(email, password) {
  if (authMode !== 'supabase') throw new Error('Accounts are created automatically in development mode.')
  const { data, error } = await (await supabase()).auth.signUp({ email, password })
  if (error) throw new Error(error.message)
  return { needsConfirmation: !data.session }
}

export async function signOut() {
  if (authMode === 'supabase') await (await supabase()).auth.signOut()
  try {
    localStorage.removeItem(DEV_KEY)
  } catch {
    /* ignore */
  }
  devMemory = null
}

export async function currentToken() {
  return (await getToken()) || devMemory
}
