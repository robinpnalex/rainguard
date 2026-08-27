import { useEffect } from 'react'
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, useMapEvents, useMap } from 'react-leaflet'
import { hazardColour, HAZARD_LABELS } from '../constants'

// Marker radius grows with severity so a glance at the map ranks the problems.
function radiusFor(hazard) {
  return 7 + hazard.severity * 0.9
}

function ClickHandler({ onMapClick }) {
  useMapEvents({
    click(event) {
      if (onMapClick) onMapClick(event.latlng.lat, event.latlng.lng)
    },
  })
  return null
}

function FlyTo({ target }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.flyTo([target.latitude, target.longitude], 17, { duration: 0.6 })
  }, [target, map])
  return null
}

export default function MapView({
  hazards, centre, selectedId, onSelect, onMapClick, pendingLocation, flyTarget, routes,
}) {
  return (
    <MapContainer
      center={[centre.latitude, centre.longitude]}
      zoom={14}
      className="map"
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ClickHandler onMapClick={onMapClick} />
      <FlyTo target={flyTarget} />

      {/* Shortest route underneath, safer route on top. */}
      {routes && (
        <>
          <Polyline
            positions={routes.shortest.coordinates}
            pathOptions={{ color: '#94a3b8', weight: 5, opacity: 0.75, dashArray: '8 6' }}
          />
          <Polyline
            positions={routes.safest.coordinates}
            pathOptions={{ color: '#22c55e', weight: 5, opacity: 0.9 }}
          />
        </>
      )}

      {hazards.map((hazard) => (
        <CircleMarker
          key={hazard.id}
          center={[hazard.latitude, hazard.longitude]}
          radius={radiusFor(hazard)}
          pathOptions={{
            color: hazard.id === selectedId ? '#ffffff' : hazardColour(hazard),
            weight: hazard.id === selectedId ? 3 : 1.5,
            fillColor: hazardColour(hazard),
            fillOpacity: hazard.status === 'VERIFIED' ? 0.45 : 0.8,
          }}
          eventHandlers={{ click: () => onSelect(hazard.id) }}
        >
          <Tooltip direction="top" offset={[0, -6]}>
            <strong>#{hazard.id} {HAZARD_LABELS[hazard.type]}</strong>
            <br />
            Severity {hazard.severity}/10 &middot; {hazard.observation_count} obs
            <br />
            {hazard.status}
          </Tooltip>
        </CircleMarker>
      ))}

      {pendingLocation && (
        <CircleMarker
          center={[pendingLocation.latitude, pendingLocation.longitude]}
          radius={9}
          pathOptions={{
            color: '#f8fafc', weight: 2, dashArray: '4 3',
            fillColor: '#f8fafc', fillOpacity: 0.25,
          }}
        >
          <Tooltip permanent direction="top" offset={[0, -8]}>
            Report location
          </Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  )
}
