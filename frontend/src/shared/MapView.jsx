import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const TILES = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png'
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'

// Leaflet renders tooltip strings as HTML; hospital names come from user input.
const escapeHtml = (t) => String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])

function pin(html, cls) {
  return L.divIcon({ html: `<div class="ba-pin ${cls}">${html}</div>`, className: '', iconSize: [36, 36], iconAnchor: [18, 18] })
}

// markers: [{ id, lat, lng, html, cls, title, onClick }]
// The map zooms to `fitPoints` ([[lat, lng], ...]) whenever `fitKey` changes.
export default function MapView({ center, zoom = 12, markers = [], incident, line, onMapClick, fitKey, fitPoints = [], className = '' }) {
  const el = useRef(null)
  const map = useRef(null)
  const layer = useRef(null)
  const clickRef = useRef(onMapClick)
  clickRef.current = onMapClick

  useEffect(() => {
    map.current = L.map(el.current, { zoomControl: true, attributionControl: true }).setView(center, zoom)
    L.tileLayer(TILES, { attribution: ATTRIBUTION, subdomains: 'abcd', maxZoom: 19 }).addTo(map.current)
    layer.current = L.layerGroup().addTo(map.current)
    map.current.on('click', (e) => clickRef.current && clickRef.current({ lat: e.latlng.lat, lng: e.latlng.lng }))
    return () => map.current.remove()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const g = layer.current
    g.clearLayers()
    if (line) L.polyline(line, { color: '#0F6E6E', weight: 5, opacity: 0.8, dashArray: '10 8' }).addTo(g)
    markers.forEach((m) => {
      const mk = L.marker([m.lat, m.lng], { icon: pin(escapeHtml(m.html), m.cls), title: m.title }).addTo(g)
      if (m.title) mk.bindTooltip(escapeHtml(m.title), { direction: 'top', offset: [0, -16] })
      if (m.onClick) mk.on('click', m.onClick)
    })
    if (incident) L.marker([incident.lat, incident.lng], { icon: pin('!', 'ba-pin-incident'), title: 'Patient location', zIndexOffset: 1000 }).addTo(g)
  }, [markers, incident, line])

  useEffect(() => {
    if (!fitKey || !fitPoints.length) return
    if (fitPoints.length === 1) map.current.setView(fitPoints[0], 13)
    else map.current.fitBounds(fitPoints, { padding: [50, 50], maxZoom: 15 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey])

  return <div ref={el} className={`rounded-2xl overflow-hidden border border-slate-200 ${className}`} />
}
