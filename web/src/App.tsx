import { dataSource } from './api/source'
import { canRecheck, unavailableReason, useBackendStatus } from './api/useBackendStatus'
import { useInvestigation } from './api/useInvestigation'
import { Home } from './components/Home'
import { Report } from './components/Report'

const replay = dataSource.kind === 'replay'

export default function App() {
  const { state, open, submit, retryLoad, close } = useInvestigation(dataSource)
  const backend = useBackendStatus(dataSource)
  const { investigation, evidence, events, submitting, researchDone, finished, loadError, error, reused } = state
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
              researchDone={researchDone}
              finished={finished}
              loadError={loadError}
              replay={replay}
              reused={reused}
              onRetry={retryLoad}
              onReplay={replay ? () => void open(investigation.id, { animate: true }) : undefined}
            />
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
          </>
        ) : (
          <Home
            unavailableReason={unavailableReason(backend.status)}
            onRetryBackend={canRecheck(backend.status) ? backend.recheck : undefined}
            submitting={submitting}
            error={error}
            recordings={dataSource.recordings}
            onSubmit={(claim) => void submit(claim, {})}
            onOpen={(id) => void open(id)}
          />
        )}
      </main>
    </>
  )
}
