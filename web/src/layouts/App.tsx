import { useCallback, useEffect, useState } from 'react'
import { dataSource } from '../api/source'
import { useBackendStatus } from '../api/useBackendStatus'
import { useInvestigation } from '../api/useInvestigation'
import { Home } from './Home'
import { ExampleReport } from './ExampleReport'
import { Icon } from './Icon'
import { Report } from './Report'
import { examples } from './examples'

type Route = { kind: 'home' } | { kind: 'example' | 'investigation' | 'pending'; value: string }

// Standalone previews use a fragment so the same file can open every report.
function readRoute(): Route {
  const params = new URLSearchParams(location.protocol === 'file:' ? location.hash.slice(1) : location.search)
  for (const kind of ['example', 'investigation'] as const) {
    const value = params.get(kind)
    if (value) return { kind, value }
  }
  const claim = history.state?.pendingClaim
  return typeof claim === 'string' ? { kind: 'pending', value: claim } : { kind: 'home' }
}

function routeUrl(next: Route) {
  const url = new URL(location.href)
  url.searchParams.delete('example')
  url.searchParams.delete('investigation')
  url.hash = ''
  if (next.kind === 'investigation' || next.kind === 'example') {
    if (url.protocol === 'file:') url.hash = new URLSearchParams({ [next.kind]: next.value }).toString()
    else url.searchParams.set(next.kind, next.value)
  }
  return url
}

export default function App() {
  const [route, setRoute] = useState<Route>(readRoute)
  const { state, open, submit, retryLoad, close } = useInvestigation(dataSource)
  const backend = useBackendStatus(dataSource)
  const example = route.kind === 'example' ? examples.find(e => e.id === route.value) : undefined
  const { investigation, evidence, events, researchDone, finished, loadError, error, reused } = state
  const live = backend.status === 'ready'
  const replay = dataSource.kind === 'replay'

  const navigate = useCallback((next: Route) => {
    history.pushState(next.kind === 'pending' ? { pendingClaim: next.value } : null, '', routeUrl(next))
    setRoute(next)
  }, [])

  useEffect(() => {
    const restore = () => { close(); setRoute(readRoute()) }
    window.addEventListener('popstate', restore)
    return () => window.removeEventListener('popstate', restore)
  }, [close])

  useEffect(() => {
    if (route.kind === 'investigation' && investigation?.id !== route.value) void open(route.value)
  }, [route, investigation?.id, open])

  const investigationId = investigation?.id
  useEffect(() => {
    if (route.kind === 'pending' && investigationId) {
      history.replaceState(null, '', routeUrl({ kind: 'investigation', value: investigationId }))
    }
  }, [route, investigationId])

  useEffect(() => {
    document.title = route.kind === 'home' ? 'ALETHEIA · Claim verification' : 'Verification results · ALETHEIA'
    window.scrollTo(0, 0)
    if (route.kind !== 'home') document.getElementById('results')?.focus({ preventScroll: true })
  }, [route])

  function newSearch() {
    close()
    if (route.kind !== 'home') navigate({ kind: 'home' })
    requestAnimationFrame(() => document.getElementById('claim')?.focus())
  }

  function verify(claim: string) {
    const normalize = (v: string) => v.toLowerCase().replace(/[.!?]+$/, '').trim()
    const match = examples.find(e => normalize(e.claim) === normalize(claim))
    if (match && !live) { navigate({ kind: 'example', value: match.id }); return }
    navigate({ kind: 'pending', value: claim })
    if (live) void submit(claim, {})
  }

  return <>
    <header className="topbar"><div className="topbar-inner">
      <button className="wordmark" type="button" onClick={newSearch} aria-label="Aletheia home">
        <Icon name="fingerprint" size={31} /><span>ALETHEIA</span>
      </button>
      <span className={'mode' + (live ? ' live' : '')}><Icon name="globe" size={15} />
        {live ? 'Live research' : 'Sample mode'}
      </span>
    </div></header>
    {route.kind === 'home' ?
      <main className="landing"><Home submitting={state.submitting} onSubmit={verify} onExample={value => navigate({ kind: 'example', value })} /></main>
      : <main className="results" id="results" tabIndex={-1}>
        <button type="button" className="back" onClick={newSearch}><Icon name="back" size={16} /> New Search</button>
        {example ? <ExampleReport key={example.id} example={example} /> : investigation ? <>
          <Report key={investigation.id} investigation={investigation} evidence={evidence} events={events} researchDone={researchDone}
            finished={finished} loadError={loadError} replay={replay} reused={reused} onRetry={retryLoad}
            onReplay={replay ? () => void open(investigation.id, { animate: true }) : undefined} />
          {error && <p className="error" role="alert">{error}</p>}
        </> : <section className="result-card status-card" aria-live="polite">
          <p className="eyebrow">Investigation</p>
          <h1 className="claim">{route.kind === 'pending' ? route.value : 'Verification results'}</h1>
          {error ? <p role="alert">{error}</p> : route.kind === 'pending'
            ? <p>{state.submitting ? 'Starting your investigation…' : live ? 'Ready to verify this claim.' :
              'Live research is unavailable. You can explore a sample investigation while the research backend is offline.'}</p>
            : <p>{route.kind === 'example' ? 'This sample could not be found.' : 'Loading investigation…'}</p>}
          {route.kind === 'pending' && !state.submitting && (live
            ? <button className="secondary-button" onClick={() => void submit(route.value, {})}>Verify claim</button>
            : !replay && <button className="secondary-button" disabled={backend.status === 'checking'} onClick={backend.recheck}>Retry connection</button>)}
          {route.kind === 'investigation' && error && <button className="secondary-button" onClick={() => void open(route.value)}>Retry loading</button>}
          {route.kind === 'pending' && !live && <div className="pills">{examples.map(e => <button className="sample" key={e.id} onClick={() => navigate({ kind: 'example', value: e.id })}><Icon name={e.icon} size={16} />{e.claim}</button>)}</div>}
        </section>}
      </main>}
  </>
}
