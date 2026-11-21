import { useCallback, useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const CANALES = [
  { value: 'internet', label: 'En línea' },
  { value: 'persona', label: 'Presencial' },
  { value: 'telefono', label: 'Teléfono' },
]

// El catálogo trae los departamentos en mayúsculas y sin tildes.
const DEPTO_LABEL = {
  PAYSANDU: 'Paysandú', 'SAN JOSE': 'San José', 'RIO NEGRO': 'Río Negro',
  TACUAREMBO: 'Tacuarembó', 'TREINTA Y TRES': 'Treinta y Tres',
}
const deptoLabel = (v) =>
  DEPTO_LABEL[v] ?? v.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase())

const EJEMPLOS_BUSCAR = ['sacar pasaporte', 'libreta de conducir', 'seguro de paro', 'carné de salud']
const EJEMPLOS_PREGUNTAR = [
  'Me quedé sin trabajo, ¿qué puedo cobrar?',
  'Tuve un bebé, ¿cómo lo registro?',
  '¿Qué necesito para viajar al exterior?',
]

function Badge({ children, color = 'gray' }) {
  const colors = {
    gray: 'bg-gray-100 text-gray-700',
    green: 'bg-emerald-100 text-emerald-700',
    blue: 'bg-blue-100 text-blue-700',
    amber: 'bg-amber-100 text-amber-800',
  }
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${colors[color]}`}>
      {children}
    </span>
  )
}

function Bar({ className = '' }) {
  return <div className={`rounded bg-gray-200 ${className}`} />
}

function ResultCard({ doc, showScore }) {
  return (
    <article className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm hover:shadow-md transition-shadow">
      <a href={doc.url} target="_blank" rel="noreferrer"
         className="text-lg font-semibold text-blue-700 hover:underline leading-snug">
        {doc.nombre}
      </a>
      <p className="mt-1 text-sm text-gray-500">
        {doc.organismo} — {doc.organismo_padre}
      </p>
      {doc.highlight ? (
        <p className="mt-2 text-sm text-gray-700"
           dangerouslySetInnerHTML={{ __html: doc.highlight }} />
      ) : (
        <p className="mt-2 text-sm text-gray-700 line-clamp-3">{doc.descripcion}</p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {doc.es_casuistica && (
          <span title="Esta página agrupa varios trámites: entrá y elegí el que corresponde a tu situación.">
            <Badge color="gray">Elegí tu caso →</Badge>
          </span>
        )}
        {doc.tiene_costo
          ? <Badge color="amber">{doc.costo ? `Costo: ${doc.costo}` : 'Con costo'}</Badge>
          : doc.costo_desconocido
            ? <Badge color="gray">Costo no informado</Badge>
            : <Badge color="green">Gratuito</Badge>}
        {doc.canales.map((c) => (
          <Badge key={c} color="blue">{CANALES.find((x) => x.value === c)?.label ?? c}</Badge>
        ))}
        {showScore && <span className="ml-auto text-xs text-gray-400">score {doc.score}</span>}
      </div>
      {doc.costo_texto && (
        <p className="mt-2 text-xs text-gray-500 line-clamp-2">{doc.costo_texto}</p>
      )}
      {doc.url_tramite && doc.url_tramite.startsWith('http') && (
        <a href={doc.url_tramite} target="_blank" rel="noreferrer"
           className="mt-2 inline-block text-sm font-medium text-emerald-700 hover:underline">
          Iniciar trámite en línea →
        </a>
      )}
    </article>
  )
}

function ResultsSkeleton() {
  return (
    <div className="animate-pulse space-y-4" aria-label="Buscando">
      <Bar className="h-4 w-28" />
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="rounded-xl border border-gray-200 bg-white p-5">
          <Bar className="h-5 w-2/3" />
          <Bar className="mt-2 h-3.5 w-1/3" />
          <Bar className="mt-4 h-3.5 w-full" />
          <Bar className="mt-2 h-3.5 w-5/6" />
          <div className="mt-4 flex gap-2">
            <Bar className="h-5 w-24 rounded-full" />
            <Bar className="h-5 w-20 rounded-full" />
          </div>
        </div>
      ))}
    </div>
  )
}

function ChatSkeleton() {
  return (
    <div className="animate-pulse space-y-4" aria-label="Generando respuesta">
      <div className="flex gap-2">
        <Bar className="h-5 w-40 rounded-full" />
        <Bar className="h-5 w-32 rounded-full" />
        <Bar className="h-5 w-36 rounded-full" />
      </div>
      <div className="space-y-2.5 rounded-xl border border-blue-100 bg-blue-50/60 p-5">
        <Bar className="h-3.5 w-full bg-blue-100" />
        <Bar className="h-3.5 w-11/12 bg-blue-100" />
        <Bar className="h-3.5 w-4/5 bg-blue-100" />
        <Bar className="mt-5 h-4 w-1/3 bg-blue-100" />
        <Bar className="h-3.5 w-full bg-blue-100" />
        <Bar className="h-3.5 w-3/4 bg-blue-100" />
      </div>
      <p className="text-xs text-gray-400">Buscando trámites y redactando la respuesta…</p>
    </div>
  )
}

function EmptyState({ title, examples, onPick }) {
  return (
    <div className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center">
      <p className="text-gray-600">{title}</p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        {examples.map((e) => (
          <button key={e} onClick={() => onPick(e)}
                  className="rounded-full bg-gray-100 px-3 py-1.5 text-sm text-gray-700 hover:bg-blue-100 hover:text-blue-800">
            {e}
          </button>
        ))}
      </div>
    </div>
  )
}

// Estilos de la respuesta del LLM (Markdown → HTML).
const MD_COMPONENTS = {
  p: (props) => <p className="my-2 leading-relaxed" {...props} />,
  h1: (props) => <h3 className="mt-4 mb-1 font-semibold text-gray-900" {...props} />,
  h2: (props) => <h3 className="mt-4 mb-1 font-semibold text-gray-900" {...props} />,
  h3: (props) => <h3 className="mt-4 mb-1 font-semibold text-gray-900" {...props} />,
  ul: (props) => <ul className="my-2 list-disc space-y-1.5 pl-5" {...props} />,
  ol: (props) => <ol className="my-2 list-decimal space-y-1.5 pl-5" {...props} />,
  strong: (props) => <strong className="font-semibold text-gray-900" {...props} />,
  a: (props) => (
    <a className="text-blue-700 hover:underline" target="_blank" rel="noreferrer" {...props} />
  ),
}

function ChatAnswer({ chat }) {
  return (
    <div className="space-y-4">
      {chat.consultas?.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
          <span>Busqué:</span>
          {chat.consultas.map((c) => <Badge key={c}>{c}</Badge>)}
        </div>
      )}
      <div className="rounded-xl border border-blue-200 bg-blue-50 p-5">
        <div className="text-gray-800 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
          <Markdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
            {chat.answer}
          </Markdown>
        </div>
        {!chat.generated && chat.answer && (
          <p className="mt-2 text-xs text-gray-400">respuesta extractiva (sin LLM)</p>
        )}
      </div>
      {chat.sources?.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Fuentes
          </h3>
          <ul className="space-y-1">
            {chat.sources.map((s, i) => (
              <li key={i}>
                <a href={s.url} target="_blank" rel="noreferrer"
                   className="text-sm text-blue-700 hover:underline">
                  [{i + 1}] {s.nombre}
                </a>
                <span className="ml-1 text-xs text-gray-400">— {s.organismo}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function FacetSection({ title, children }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</h3>
      {children}
    </div>
  )
}

function Check({ checked, onChange, children }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
      <input type="checkbox" checked={checked} onChange={onChange}
             className="rounded border-gray-300" />
      {children}
    </label>
  )
}

function FacetList({ items, selected, onSelect, label = (v) => v, limit = 8 }) {
  const [expanded, setExpanded] = useState(false)
  if (!items) {
    return (
      <div className="animate-pulse space-y-2">
        {[0, 1, 2, 3, 4].map((i) => <Bar key={i} className="h-5 w-full" />)}
      </div>
    )
  }
  if (items.length === 0) return <p className="text-sm text-gray-400">Sin resultados</p>
  const shown = expanded ? items : items.slice(0, limit)
  return (
    <div className="space-y-0.5">
      {shown.map((f) => (
        <button key={f.value} title={label(f.value)}
                onClick={() => onSelect(selected === f.value ? null : f.value)}
                className={`flex w-full items-baseline gap-1 rounded px-2 py-1 text-left text-sm ${
                  selected === f.value
                    ? 'bg-blue-100 font-medium text-blue-800'
                    : 'text-gray-600 hover:bg-gray-100'}`}>
          <span className="truncate">{label(f.value)}</span>
          <span className="ml-auto shrink-0 text-xs text-gray-400">{f.count}</span>
        </button>
      ))}
      {items.length > limit && (
        <button onClick={() => setExpanded(!expanded)}
                className="px-2 pt-1 text-xs font-medium text-blue-700 hover:underline">
          {expanded ? 'Ver menos' : `Ver ${items.length - limit} más`}
        </button>
      )}
    </div>
  )
}

export default function App() {
  const [mode, setMode] = useState('search') // 'search' | 'chat'
  // Un input por modo: cambiar de pestaña no pierde lo escrito.
  const [searchQuery, setSearchQuery] = useState('')
  const [chatQuery, setChatQuery] = useState('')
  const [data, setData] = useState(null)
  const [chat, setChat] = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [chatLoading, setChatLoading] = useState(false)
  const [organismo, setOrganismo] = useState(null)
  const [canal, setCanal] = useState(null)
  const [gratuito, setGratuito] = useState(false)
  const [hybrid, setHybrid] = useState(true)
  const [doRerank, setDoRerank] = useState(false)
  const debounce = useRef(null)
  const lastRequest = useRef(0)

  const hasQuery = searchQuery.trim() !== ''
  const hasFilters = Boolean(organismo || canal || gratuito)

  const doSearch = useCallback((q, f) => {
    const browsing = q.trim() !== '' || f.organismo || f.canal || f.gratuito
    const params = new URLSearchParams({ q, top_k: browsing ? 20 : 0 })
    if (f.organismo) params.set('organismo', f.organismo)
    if (f.canal) params.set('canal', f.canal)
    if (f.gratuito) params.set('gratuito', 'true')
    if (f.hybrid) params.set('hybrid', 'true')
    if (f.doRerank) params.set('do_rerank', 'true')
    // Ignora respuestas de búsquedas anteriores que lleguen tarde.
    const id = ++lastRequest.current
    setSearchLoading(true)
    fetch(`/api/search?${params}`)
      .then((r) => r.json())
      .then((d) => { if (id === lastRequest.current) setData(d) })
      .catch(() => { if (id === lastRequest.current) setData({ error: true, results: [] }) })
      .finally(() => { if (id === lastRequest.current) setSearchLoading(false) })
  }, [])

  const doChat = useCallback((q) => {
    if (!q.trim()) return
    setChatLoading(true)
    fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: q }),
    })
      .then((r) => r.json())
      .then(setChat)
      .catch(() => setChat({ answer: 'Error al consultar la API.', sources: [] }))
      .finally(() => setChatLoading(false))
  }, [])

  useEffect(() => {
    clearTimeout(debounce.current)
    // Skeleton desde el primer cambio, no recién cuando sale el request.
    setSearchLoading(true)
    debounce.current = setTimeout(
      () => doSearch(searchQuery, { organismo, canal, gratuito, hybrid, doRerank }), 300)
    return () => clearTimeout(debounce.current)
  }, [searchQuery, organismo, canal, gratuito, hybrid, doRerank, doSearch])

  const facets = data && !data.error ? data.facets : null
  const query = mode === 'search' ? searchQuery : chatQuery
  const setQuery = mode === 'search' ? setSearchQuery : setChatQuery

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-5xl px-4 py-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Trámites <span className="text-blue-700">Uruguay</span>
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Buscador sobre el catálogo de trámites y servicios del Estado
            {mode === 'search' && data?.backend && (
              <span className="ml-2 text-xs text-gray-400">· motor: {data.backend}</span>
            )}
          </p>
          <div className="mt-4 flex gap-2">
            {[{ v: 'search', l: 'Buscar' }, { v: 'chat', l: 'Preguntar' }].map((m) => (
              <button key={m.v} onClick={() => setMode(m.v)}
                      className={`rounded-full px-4 py-1.5 text-sm font-medium ${
                        mode === m.v
                          ? 'bg-blue-700 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
                {m.l}
              </button>
            ))}
            {mode === 'search' && (
              <div className="ml-auto flex items-center gap-3 text-sm text-gray-500">
                <Check checked={hybrid} onChange={() => setHybrid(!hybrid)}>híbrida</Check>
                <Check checked={doRerank} onChange={() => setDoRerank(!doRerank)}>rerank</Check>
              </div>
            )}
          </div>
          <div className="mt-4 flex gap-3">
            <input
              key={mode}
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && mode === 'chat') doChat(chatQuery) }}
              placeholder={mode === 'search'
                ? 'Ej: sacar pasaporte, licencia de conducir, pagar multa…'
                : 'Preguntá en lenguaje natural: ¿qué necesito para viajar al exterior?'}
              className="min-w-0 flex-1 rounded-xl border border-gray-300 bg-white px-5 py-3.5 text-lg shadow-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
            />
            {mode === 'chat' && (
              <button onClick={() => doChat(chatQuery)} disabled={chatLoading || !chatQuery.trim()}
                      className="rounded-xl bg-blue-700 px-6 font-medium text-white hover:bg-blue-800 disabled:opacity-50">
                Preguntar
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-5xl gap-6 px-4 py-6">
        {mode === 'chat' ? (
          <section className="min-w-0 flex-1">
            {chatLoading ? <ChatSkeleton />
              : chat ? <ChatAnswer chat={chat} />
              : (
                <EmptyState
                  title="Hacé una pregunta y te explico qué trámite corresponde."
                  examples={EJEMPLOS_PREGUNTAR}
                  onPick={(e) => { setChatQuery(e); doChat(e) }} />
              )}
          </section>
        ) : (
          <>
            <aside className="w-60 shrink-0 space-y-6">
              <FacetSection title="Canal de atención">
                <div className="space-y-1">
                  {CANALES.map((c) => (
                    <Check key={c.value} checked={canal === c.value}
                           onChange={() => setCanal(canal === c.value ? null : c.value)}>
                      {c.label}
                    </Check>
                  ))}
                </div>
              </FacetSection>
              <FacetSection title="Costo">
                <Check checked={gratuito} onChange={() => setGratuito(!gratuito)}>
                  Solo gratuitos
                </Check>
              </FacetSection>
              <FacetSection title="Departamento">
                <FacetList items={facets?.departamentos} selected={organismo}
                           onSelect={setOrganismo} label={deptoLabel} limit={19} />
              </FacetSection>
              <FacetSection title="Organismo">
                <FacetList items={facets?.organismos} selected={organismo}
                           onSelect={setOrganismo} />
              </FacetSection>
              {hasFilters && (
                <button onClick={() => { setOrganismo(null); setCanal(null); setGratuito(false) }}
                        className="text-sm font-medium text-blue-700 hover:underline">
                  Limpiar filtros
                </button>
              )}
            </aside>

            <section className="min-w-0 flex-1 space-y-4">
              {searchLoading ? <ResultsSkeleton />
                : data?.error ? (
                  <p className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
                    Error al consultar la API. ¿Está corriendo uvicorn en :8000?
                  </p>
                )
                : !hasQuery && !hasFilters ? (
                  <EmptyState
                    title="Escribí qué trámite buscás o elegí un filtro para explorar el catálogo."
                    examples={EJEMPLOS_BUSCAR}
                    onPick={setSearchQuery} />
                )
                : data && (
                  <>
                    <p className="text-sm text-gray-500">
                      {data.total} resultado{data.total !== 1 ? 's' : ''}
                    </p>
                    {data.results.map((doc) => <ResultCard key={doc.id} doc={doc} showScore={hasQuery} />)}
                    {data.results.length === 0 && (
                      <p className="text-gray-500">Sin resultados. Probá con otros términos o filtros.</p>
                    )}
                  </>
                )}
            </section>
          </>
        )}
      </main>
    </div>
  )
}
