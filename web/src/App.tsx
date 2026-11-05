import { dataSource } from './api/source'
import { useInvestigation } from './api/useInvestigation'
import { LiveHome, ReplayHome } from './components/Home'
import { Report } from './components/Report'

const replay = dataSource.kind === 'replay'

export default function App() {
  const { state, open, submit, close } = useInvestigation(dataSource)
  const { investigation, evidence, events, finished, error } = state
  const recording = dataSource.recordings.find((r) => r.investigation.id === investigation?.id)
  const showingSample = recording ? recording.sample : dataSource.recordings.some((r) => r.sample)

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <button type="button" className="wordmark" onClick={close} aria-label="Aletheia home">
            Aletheia
          </button>
          {replay && (
            <p className="notice" role="status">
              <strong>Recorded investigation</strong>
              {showingSample && ' · Invented sample data'}
              <span className="notice-detail"> · New research isn’t available on this page.</span>
            </p>
          )}
        </div>
      </header>

      <main>
        {investigation ? (
          <>
            <button type="button" className="back" onClick={close}>
              ← {replay ? 'All sample investigations' : 'Check another claim'}
            </button>
            <Report
              investigation={investigation}
              evidence={evidence}
              events={events}
              finished={finished}
              replay={replay}
            />
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
          </>
        ) : replay ? (
          <ReplayHome recordings={dataSource.recordings} onOpen={(id) => void open(id)} />
        ) : (
          <LiveHome error={error} onSubmit={(claim) => void submit(claim, {})} />
        )}
      </main>
    </>
  )
}
