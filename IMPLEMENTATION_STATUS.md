# Implementation status

What the SIH abstract claims, versus what is actually in this repo.
Checked against the code on 28 Aug 2026.

## Summary

| | Count |
|---|---|
| Built as described | 3 |
| Built, but differently than the abstract says | 2 |
| Not built | 3 |

---

## Stack claims

### Built as described

**Python / FastAPI backend**
`backend/main.py:34`. Endpoints for detections, hazards, repair, verification,
routing, stats and the demo replay. SQLAlchemy models in `backend/models.py`.

**React + Leaflet live map dashboard**
`frontend/src/components/MapView.jsx:37` — OpenStreetMap raster tiles, hazards
drawn as `CircleMarker`s sized by severity and coloured by repair status
(`frontend/src/constants.js`). Table, detail panel, report form and demo
controls in `frontend/src/components/`.

**OSMnx + NetworkX over an OpenStreetMap Manipal extract**
`backend/routing.py:67` pulls 4 km of drivable roads with
`ox.graph_from_point`, cached to `model/manipal_graph.graphml` so it works
offline. `build_safe_costs()` penalises edges near severe hazards, then
compares shortest vs. hazard-avoiding paths. Exposed at
`backend/main.py:443`, which reads live hazards from the database on every
request — so route avoidance does update in real time.

### Built, but differently than the abstract says

**"PostgreSQL + PostGIS for geo-data" → actually SQLite + trigonometry**
`backend/config.py:12` uses SQLite. Distance maths is hand-rolled haversine in
`backend/geo.py`, whose first line reads *"No PostGIS, no GeoPandas — just
trigonometry."* This was a deliberate choice: the original build spec
explicitly ruled out PostGIS to keep the project readable for students.
Proximity queries use a bounding-box SQL prefilter plus an exact haversine
check (`backend/dedup.py`).

**"DBSCAN-based clustering for report deduplication" → actually radius matching**
`backend/dedup.py:4` says *"Deliberately not a clustering algorithm."* When a
detection arrives, `find_matching_hazard()` looks for an existing hazard of the
same type within 25 m and folds the new sighting into it. Same outcome as
clustering for this use case, but it is not DBSCAN and there is no scikit-learn
clustering anywhere in the codebase.

The 25 m radius (not the spec's 10 m) is because consumer GPS is accurate to
roughly 5–15 m outdoors — see the comment at `backend/config.py:23`.

### Not built

**Fine-tuned YOLOv8/v11-nano on Roboflow + RDD2022**
No trained weights exist. `model/` contains no `.pt` file, and
`backend/config.py:32` is set to `DETECTOR_MODE = "mock"`.

What *is* ready:
- `backend/detector/yolo_detector.py` — full Ultralytics integration behind the
  same `Detector` interface, with a class-name map and automatic fallback to
  mock if the weights fail to load.
- `model/train.py` — downloads a Roboflow dataset, fine-tunes YOLOv8n, installs
  the weights to `model/nirvana.pt`.
- `backend/requirements-yolo.txt` — the optional torch dependencies.

So detection is currently **simulated**. `backend/detector/mock_detector.py`
reads filename hints and falls back to a SHA-256 hash of the image bytes, which
makes it deterministic — the same photo always gives the same answer.

**On-device / edge inference for a drive-mode capture app**
Does not exist. There is no mobile app and no video ingest. Uploads are single
photos through the dashboard or `POST /detections`.

**OpenWeather / IMD API for rainfall correlation**
No code at all. `backend/severity.py` scores hazards from type, confidence and
repeat sightings only; its docstring notes rainfall as a possible future input,
but nothing calls a weather API.

---

## Methodology chain

| Step | Status | Where |
|---|---|---|
| 1. Capture | Built | `POST /detections`, `backend/main.py:176` |
| 2. Detect & geo-tag | Partial | Geo-tagging built (`backend/location.py:25`, three-tier: explicit coords → EXIF GPS → browser). Detection is mock. |
| 3. Cluster / dedupe | Built | `backend/dedup.py`, radius-based (see above) |
| 4. Dashboard triage | Built | `frontend/src/App.jsx`, severity ranking in `backend/severity.py` |
| 5. Repair | Built | `hazard_service.mark_repaired()`, `backend/hazard_service.py:157` |
| 6. Photo re-verification, auto pass/fail | Partial | Workflow built: `POST /hazards/{id}/verify` at `backend/main.py:315`, `record_clean_observation()` at `backend/hazard_service.py:116`. Three clean observations → VERIFIED; a fresh detection sends it back to CONFIRMED. The pass/fail decision comes from the mock detector, not a trained model. |
| 7. Route-avoidance updated in real time | Built | `backend/main.py:443` re-reads open hazards per request |

The full lifecycle is
`SUSPECTED → CONFIRMED → REPAIR_PENDING → REPAIRED → VERIFIED`,
with a failed verification path back to `CONFIRMED`.

---

## Known gaps to close

1. **Train the model.** Detection is the core claim of the abstract, and it is
   the one gap a judge is most likely to find. `model/train.py` plus a free
   Colab T4 is an afternoon of work. See `model/README.md`.
2. **Fix the abstract, or fix the code.** PostGIS and DBSCAN are not in this
   repo. Either implement them or describe what was actually built — SQLite
   with haversine proximity matching is a defensible prototype choice, and
   defending a real decision is easier than explaining a claim that is not
   backed by code.
3. **Rainfall correlation** is the cheapest remaining item: one OpenWeather
   call, feeding a multiplier into `backend/severity.py`.
