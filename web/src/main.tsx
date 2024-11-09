import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, Document, Graph, Edge, Passage, Run } from './api';
import './style.css';

const emptyGraph: Graph = { generation: 0, nodes: [], edges: [], communities: [] };
const blank = { id: '', title: '', text: '', revision: 0 };
function App() {
  const [tab, setTab] = useState('Graph');
  const [documents, setDocuments] = useState<Document[]>([]);
  const [graph, setGraph] = useState<Graph>(emptyGraph);
  const [jobs, setJobs] = useState<any[]>([]);
  const [corrections, setCorrections] = useState<any[]>([]);
  const [selected, setSelected] = useState('');
  const [passage, setPassage] = useState<Passage | null>(null);
  const [draft, setDraft] = useState(blank);
  const [question, setQuestion] = useState('Who owns Lumen?');
  const [results, setResults] = useState<Run[]>([]);
  const [report, setReport] = useState<Run | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState('');
  const [loaded, setLoaded] = useState(false);
  const generation = useRef(0);
  const actionLock = useRef(false);
  const sourceTrigger = useRef<HTMLElement | null>(null);

  async function refresh() {
    const [docs, nextGraph, nextJobs, history] = await Promise.all([api<Document[]>('/documents'), api<Graph>('/graph'), api<any[]>('/jobs'), api<any[]>('/corrections')]);
    if (generation.current !== nextGraph.generation) { setResults([]); setReport(null); setPassage(null); }
    generation.current = nextGraph.generation;
    setDocuments(docs); setGraph(nextGraph); setJobs(nextJobs); setCorrections(history); setLoaded(true);
  }
  useEffect(() => {
    let alive = true;
    refresh().catch(e => alive && setError(e.message));
    const timer = setInterval(async () => {
      try { const health = await api('/health'); if (alive && health.generation !== generation.current) await refresh(); else if (alive) setJobs(await api('/jobs')); }
      catch (e) { if (alive) setError((e as Error).message); }
    }, 5000);
    return () => { alive = false; clearInterval(timer); };
  }, []);
  async function act(label: string, operation: () => Promise<void>) {
    if (actionLock.current) return;
    actionLock.current = true; setBusy(label); setError(''); setNotice('');
    try { await operation(); } catch (e) { setError((e as Error).message); }
    finally { setBusy(''); actionLock.current = false; }
  }
  function closePassage() { setPassage(null); requestAnimationFrame(() => { if (sourceTrigger.current?.isConnected) sourceTrigger.current.focus(); }); }
  async function openPassage(id: string) { sourceTrigger.current = document.activeElement as HTMLElement; await act('Opening evidence', async () => setPassage(await api(`/passages/${encodeURIComponent(id)}`))); }
  async function correct(edge: Edge) {
    const reason = window.prompt('Why should this relationship be excluded?');
    if (!reason?.trim()) return;
    await act('Saving correction', async () => {
      await api('/corrections', { claim_id: edge.claim_id, status: 'rejected', reason, expected_generation: graph.generation });
      await refresh(); setNotice('Correction saved. The disputed passage is excluded from all query modes.');
    });
  }
  async function compare(mode: string) {
    await act(mode === 'all' ? 'Comparing three retrieval modes' : `Running ${mode} search`, async () => {
      setResults([]);
      for (const choice of mode === 'all' ? ['vector', 'local', 'global'] : [mode]) {
        const result = await api<Run>('/query', { question, mode: choice });
        const health = await api('/health');
        if (health.generation !== result.generation) { await refresh(); throw new Error('The corpus changed during comparison. Run it again against current evidence.'); }
        setResults(old => [...old, result]);
      }
    });
  }
  const edges = selected ? graph.edges.filter(e => e.source === selected || e.target === selected) : graph.edges;
  const positions = new Map(graph.nodes.map((node, index) => { const angle = index * Math.PI * 2 / Math.max(1, graph.nodes.length) - Math.PI / 2; return [node.id, { x: 380 + 290 * Math.cos(angle), y: 240 + 170 * Math.sin(angle) }]; }));
  const pending = jobs.filter(j => ['queued', 'running'].includes(j.status)).length;
  return <div className="shell">
    <aside className="sidebar"><a className="brand" href="/" aria-label="Evidence Explorer home"><span className="brand-mark">e<span>·</span></span><span>Evidence<br />Explorer</span></a>
      <p className="nav-label">WORKSPACE</p><nav aria-label="Main navigation">{['Graph', 'Documents', 'Compare', 'Indexing', 'Corrections'].map(name => <button key={name} className={tab === name ? 'active' : ''} aria-current={tab === name ? 'page' : undefined} onClick={() => { setTab(name); setPassage(null); window.scrollTo({ top: 0 }); }}>{name}<span>{name === 'Documents' ? documents.length : name === 'Indexing' ? pending || '' : '↗'}</span></button>)}</nav>
      <div className="sidebar-note"><span className="dot" />Local evidence workspace<p>Follow every relationship back to its source.</p></div>
    </aside>
    <main><header><div><p className="eyebrow">CORPUS INTELLIGENCE / {tab.toUpperCase()}</p><h1>{tab === 'Graph' ? 'See how the evidence connects.' : tab === 'Documents' ? 'Start with the source.' : tab === 'Compare' ? 'Three paths. The same evidence.' : tab === 'Indexing' ? 'Every step, accounted for.' : 'Keep the record accountable.'}</h1></div><button className="quiet" disabled={!!busy} onClick={() => act('Refreshing', refresh)}>Refresh ↻</button></header>
      <div className="status-line"><span>{documents.length} documents</span><span>{graph.nodes.length} entities</span><span>{graph.edges.length} supported relationships</span><span className="status-right">{pending ? `${pending} indexing` : 'Evidence ready'}</span></div>
      {error && <div role="alert" className="alert">{error}</div>}{notice && <div role="status" className="notice">{notice}</div>}{busy && <div role="status" className="working">{busy}…</div>}
      {!loaded && <p className="empty">Loading your evidence workspace…</p>}
      {loaded && !documents.length && <div className="welcome"><p className="eyebrow">A SMALL CORPUS. A CLEAR TRAIL.</p><h2>Your evidence starts here.</h2><p>Add your own documents or explore the original service-ownership sample.</p><button disabled={!!busy} onClick={() => act('Loading example documents', async () => { await api('/demo', {}); await refresh(); setTab('Indexing'); setNotice('Example documents queued. Keep the indexing worker running to extract relationships.'); })}>Load sample corpus</button><button className="quiet" onClick={() => setTab('Documents')}>Add a document</button></div>}
      {tab === 'Graph' && <>
        <div className="graph-grid"><section className="panel graph-panel"><div className="panel-heading"><div><p className="eyebrow">RELATIONSHIP MAP</p><h2>{selected ? graph.nodes.find(n => n.id === selected)?.label : 'The connected corpus'}</h2></div><button className="quiet" onClick={() => setSelected('')}>Show all</button></div>
          {graph.nodes.length ? <svg viewBox="0 0 760 480" role="img" aria-label="Interactive evidence relationship map"><title>Choose an entity to inspect its relationships</title>{graph.edges.map(e => { const a = positions.get(e.source)!; const b = positions.get(e.target)!; return <line key={e.claim_id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={selected && (e.source === selected || e.target === selected) ? 'edge selected' : 'edge'} />; })}{graph.nodes.map(node => { const p = positions.get(node.id)!; return <g key={node.id} role="button" tabIndex={0} aria-label={`Inspect ${node.label}`} aria-pressed={selected === node.id} onClick={() => setSelected(node.id)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(node.id); } }} className={selected === node.id ? 'node selected' : 'node'}><circle cx={p.x} cy={p.y} r={node.id === selected ? 12 : 8} /><text x={p.x} y={p.y + 27} textAnchor="middle">{node.label}</text></g>; })}</svg> : <div className="empty">Relationships appear after source indexing completes.</div>}
          <p className="caption">Each line has a supporting source passage. A missing line can mean extraction missed the relationship.</p></section>
          <section className="panel evidence-list"><div className="panel-heading"><div><p className="eyebrow">SOURCE TRAIL</p><h2>{selected ? 'Connected evidence' : 'Inspect a relationship'}</h2></div><span className="count">{edges.length}</span></div>{edges.slice(0, 40).map(edge => <article className="relationship" key={edge.claim_id}><h3>{edge.source} <span>{edge.relation}</span> {edge.target}</h3><p>{edge.support}</p><div className="row-actions"><button className="text-button" disabled={!!busy} onClick={() => openPassage(edge.chunk_id)}>Read source ↗</button><button className="text-button danger" disabled={!!busy} onClick={() => correct(edge)}>Flag relationship</button></div></article>)}{!edges.length && <p className="empty">Select an indexed entity to inspect its evidence.</p>}</section></div>
        <section className="communities"><div className="section-heading"><h2>Communities of evidence</h2><p>Grouped relationships, with original passages attached.</p></div><div className="community-grid">{graph.communities.map((community, i) => <article className="panel community" key={community.id}><p className="eyebrow">COMMUNITY {String(i + 1).padStart(2, '0')}</p><h3>{community.nodes.slice(0, 3).join(' · ')}</h3><p>{community.nodes.length} entities · {community.claim_ids.length} relationships</p><button className="quiet" disabled={!!busy} onClick={() => act('Drafting community report', async () => setReport(await api('/community-report', { community_id: community.id, expected_generation: graph.generation })))}>Draft evidence summary ↗</button></article>)}</div>{report && <div className="panel report"><p className="eyebrow">COMMUNITY REPORT · {report.status}</p>{report.result ? <><h3>{report.result.report.title}</h3><p>{report.result.report.summary}</p><p className="caption">Model draft. Verify its statements against the source evidence below.</p>{report.result.source_support.map((text: string, i: number) => <blockquote key={i}>{text}</blockquote>)}</> : <p>The model did not return a valid report. Source relationships remain available.</p>}</div>}</section>
      </>}
      {tab === 'Documents' && <div className="document-grid"><section className="panel"><div className="panel-heading"><h2>Source library</h2><span className="count">{documents.length}</span></div><div className="document-list">{documents.map(doc => <button className="document-row" key={doc.id} disabled={!!busy} onClick={() => act('Loading document', async () => { const value = await api<any>(`/documents/${doc.id}`); setDraft({ id: value.document_id, title: value.title, text: value.text, revision: value.revision }); })}><span><strong>{doc.title}</strong><small>{doc.id} · revision {doc.revision} · {doc.characters} characters</small></span><span>↗</span></button>)}</div></section><section className="panel editor"><div className="panel-heading"><h2>{draft.revision ? 'Edit document' : 'Add a document'}</h2><button className="quiet" onClick={() => setDraft(blank)}>New document</button></div><form onSubmit={e => { e.preventDefault(); act('Saving and queuing document', async () => { await api('/documents', { ...draft, expected_revision: draft.revision }); await api('/index', { document_id: draft.id }); await refresh(); setDraft(blank); setNotice('Document saved and queued for indexing.'); }); }}><label>Document ID<input value={draft.id} disabled={!!draft.revision} required pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,79}" onChange={e => setDraft({ ...draft, id: e.target.value })} /></label><label>Title<input value={draft.title} required maxLength={160} onChange={e => setDraft({ ...draft, title: e.target.value })} /></label><label>Source text<textarea value={draft.text} required maxLength={50000} rows={10} onChange={e => setDraft({ ...draft, text: e.target.value })} /></label><p className="caption">Changes immediately invalidate the old evidence. New relationships appear after indexing.</p><div className="row-actions"><button disabled={!!busy}>Save &amp; index</button>{!!draft.revision && <button className="quiet danger" type="button" disabled={!!busy} onClick={() => { if (window.confirm(`Remove ${draft.title} from the active corpus?`)) act('Deleting document', async () => { await api(`/documents/${draft.id}/delete`, { expected_revision: draft.revision }); await refresh(); setDraft(blank); setNotice('Document removed from current evidence.'); }); }}>Delete document</button>}</div></form></section></div>}
      {tab === 'Compare' && <><section className="panel query-form"><p className="eyebrow">FOLLOW THE ANSWER</p><h2>Ask the corpus.</h2><p>Compare ordinary vector retrieval, local relationships, and community evidence.</p><label htmlFor="question">Question</label><textarea id="question" rows={2} maxLength={500} value={question} onChange={e => setQuestion(e.target.value)} /><div className="row-actions"><button disabled={!!busy || !question.trim()} onClick={() => compare('all')}>Compare all three ↗</button>{['vector', 'local', 'global'].map(mode => <button className="quiet" key={mode} disabled={!!busy || !question.trim()} onClick={() => compare(mode)}>{mode}</button>)}</div><p className="caption">Answers are model drafts. Linked citations establish where to check them; they do not prove correctness.</p></section><div className="results-grid">{results.map(run => <article className="panel answer" key={run.id}><div className="panel-heading"><h2>{run.mode}</h2><span className={`badge ${run.status}`}>{run.status}</span></div>{run.result?.answer ? <p className="answer-text">{run.result.answer}</p> : <p className="answer-failure">{run.status === 'stale' ? 'The source changed. Run the query again.' : 'The model answer failed validation. Inspect the retrieved evidence below.'}</p>}{run.result?.citations?.length > 0 && <p className="caption">Cited sources: {run.result.citations.join(', ')}</p>}<p className="caption">{run.calls.length} model calls · {run.result?.seconds?.toFixed(2) ?? '—'} seconds</p>{run.result?.passages?.map((item: Passage) => <button className="source-result" key={item.chunk_id} disabled={!!busy} onClick={() => openPassage(item.chunk_id)}><strong>[{item.citation}] {item.title}</strong><span>{item.text}</span></button>)}</article>)}</div></>}
      {tab === 'Indexing' && <section className="panel"><div className="panel-heading"><div><h2>Indexing activity</h2><p>Completed passages survive a worker restart. Cancelled jobs cannot publish evidence.</p></div></div><div className="table-scroll"><table><thead><tr><th>Document</th><th>Status</th><th>Model usage</th><th>Attempt</th><th>Action</th></tr></thead><tbody>{jobs.map(job => <tr key={job.id}><td><strong>{job.document_id}</strong><small>Revision {job.revision}</small></td><td><span className={`badge ${job.status}`}>{job.status}</span>{job.error && <small>{job.error.replaceAll('_', ' ')}</small>}</td><td>{job.usage.calls ?? 0} calls<small>{job.usage.actual_tokens ?? 0} tokens</small></td><td>{job.attempt} / 3</td><td>{['queued', 'running'].includes(job.status) ? <button className="quiet" disabled={!!busy} onClick={() => act('Cancelling index job', async () => { await api(`/jobs/${job.id}/cancel`, {}); await refresh(); })}>Cancel</button> : ['failed', 'cancelled'].includes(job.status) && job.attempt < 3 ? <button className="quiet" disabled={!!busy} onClick={() => act('Retrying index job', async () => { await api(`/jobs/${job.id}/retry`, {}); await refresh(); })}>Retry</button> : '—'}</td></tr>)}</tbody></table></div></section>}
      {tab === 'Corrections' && <section className="panel"><div className="panel-heading"><div><h2>Correction history</h2><p>Decisions append to the record. Rejected passages stay out of every retrieval mode.</p></div></div>{corrections.map((item, index) => <article className="correction" key={item.sequence}><div><span className={`badge ${item.status}`}>{item.status}</span><p>{item.reason}</p><small>Decision {item.sequence}</small></div>{item.status === 'rejected' && !corrections.slice(0, index).some(c => c.claim_id === item.claim_id) && <button className="quiet" disabled={!!busy} onClick={() => { const reason = window.prompt('Why should this evidence be restored?'); if (reason?.trim()) act('Restoring evidence', async () => { await api('/corrections', { claim_id: item.claim_id, status: 'accepted', reason, expected_generation: graph.generation }); await refresh(); }); }}>Restore evidence</button>}</article>)}{!corrections.length && <p className="empty">No corrections recorded. Flag a relationship from its source trail when it needs review.</p>}</section>}
      <footer><span>Evidence before conclusions.</span><span>Local workspace · {graph.communities.length} communities</span></footer>
    </main>
    {passage && <div className="dialog-backdrop" onClick={closePassage}><section role="dialog" aria-modal="true" aria-labelledby="source-title" className="source-dialog" onClick={e => e.stopPropagation()} onKeyDown={e => { if (e.key === 'Escape') closePassage(); if (e.key === 'Tab') { e.preventDefault(); e.currentTarget.querySelector<HTMLButtonElement>('button')?.focus(); } }}><button className="close" autoFocus onClick={closePassage} aria-label="Close source">×</button><p className="eyebrow">ORIGINAL SOURCE · REVISION {passage.revision}</p><h2 id="source-title">{passage.title}</h2><blockquote>{passage.text}</blockquote><p className="caption">Document: {passage.document_id}</p></section></div>}
  </div>;
}
createRoot(document.getElementById('root')!).render(<App />);
