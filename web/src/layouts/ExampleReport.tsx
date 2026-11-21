import type { Example } from './examples'
import { Evidence } from './Evidence'
import { SourceCitation } from './Cite'
import { Limitations } from './Report'

export function ExampleReport({ example }: { example: Example }) {
  return <article className="report">
    <section className="result-card">
      <p className="eyebrow">Sample investigation</p>
      <h1 className="claim">{example.claim}</h1>
      <div className="decision-line">
        <span className={'verdict verdict-' + example.verdict}>{example.verdict}</span>
        <span className="meta">{example.pages.length} sources</span>
      </div>
      <p className="summary">{example.summary.map(unit => <span key={unit.text}>{unit.text}{unit.cites.map(n => <SourceCitation key={n} number={n} />)}{' '}</span>)}</p>
    </section>
    <Evidence pages={example.pages} />
    <Limitations items={['This sample uses saved excerpts. The verdict reflects what these pages said when reviewed.']} />
  </article>
}
