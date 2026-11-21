import scan from './scan.png'
import { examples } from './examples'
import { ClaimForm } from './ClaimForm'
import { Icon } from './Icon'

interface Props {
  submitting: boolean
  onSubmit: (claim: string) => void
  onExample: (id: string) => void
}

export function Home({ submitting, onSubmit, onExample }: Props) {
  return (
    <section className="home">
      <div className="hero">
        <img className="print-art" src={scan} alt="" width="560" height="222" />
        <h1>Verify any claim against <em>live web sources</em></h1>
        <ClaimForm onSubmit={onSubmit} submitting={submitting} />
        <div className="examples">
          <p className="sample-label"><span />Try a sample claim<span /></p>
          <div className="pills">{examples.map(sample =>
            <button key={sample.id} className="sample" onClick={() => onExample(sample.id)}>
              <Icon name={sample.icon} size={16} />{sample.claim}
            </button>
          )}</div>
        </div>
      </div>
    </section>
  )
}
