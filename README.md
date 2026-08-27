# RainGuard

**AI-assisted road hazard monitoring for Manipal.** Smart India Hackathon 2026 prototype.

RainGuard turns scattered road photos into a live, de-duplicated hazard map —
and, crucially, closes the loop: a hazard is not "fixed" because someone
clicked a button, but because later observations prove it.

```
detect hazard → marker appears → repeated sightings strengthen it
→ municipality marks it repaired → later observations verify the repair
→ marker becomes resolved
```

---

## What it does

| Feature | What happens |
|---|---|
| **Detection** | An uploaded road photo is classified as `pothole`, `manhole` (open/damaged) or `waterlogging`, with a confidence score. |
| **Deduplication** | A new detection within **25 m** of an existing hazard of the same type becomes another *observation* of it, not a duplicate marker. |
| **Confirmation** | 1 observation → `SUSPECTED`. 3+ observations → `CONFIRMED`. |
| **Severity** | A 1–10 score from hazard type, detector confidence and how often it has been reported. An open manhole outranks a small pothole. |
| **Repair workflow** | "Mark as repaired" sets `REPAIR_PENDING`. It is only closed once re-inspections prove it. |
| **Repair verification** | A re-inspection that still detects the hazard **fails** the check and reopens it. Three clean re-inspections mark it `VERIFIED`. |
| **Safe routing** *(optional)* | Compares the shortest route with one that detours around high-severity hazards. |

### Hazard lifecycle

```
                    ┌──────────────┐
   new detection ──►│  SUSPECTED   │
                    └──────┬───────┘
                     3 observations
                    ┌──────▼───────┐
                    │  CONFIRMED   │◄────────────────┐
                    └──────┬───────┘                 │
                "mark as repaired"          hazard detected again
                    ┌──────▼────────┐        (repair check FAILED,
                    │ REPAIR_PENDING│         clean counter resets)
                    └──────┬────────┘                │
                   1 clean re-inspection             │
                    ┌──────▼───────┐                 │
                    │   REPAIRED   │─────────────────┘
                    └──────┬───────┘
                   3 clean re-inspections
                    ┌──────▼───────┐
                    │   VERIFIED   │  (closed; excluded from deduplication)
                    └──────────────┘
```

---

## Architecture

```
Road image
    │
    ▼
Detector interface ──── MockDetector (default, no ML deps)
    │              └─── YoloDetector (Ultralytics + your weights)
    ▼
FastAPI backend
    │
    ▼
Deduplication (same type, within 25 m)  ──► Severity scoring (1–10)
    │
    ▼
SQLite  (hazards + observations)
    │
    ├──────────────────────┐
    ▼                      ▼
React + Leaflet       Safe routing
dashboard             (osmnx + networkx, optional)
```

```
rainguard/
  backend/      FastAPI, SQLite, detection, dedup, severity, routing
  frontend/     React + Vite + Leaflet dashboard
  model/        YOLO weights + cached OSM street graph (both gitignored)
  sample_data/  Generated sample road photos
```

**Key backend modules** — each is small and does one thing:

| File | Responsibility |
|---|---|
| `config.py` | Every tunable constant (dedup radius, thresholds, detector mode). |
| `models.py` | The two tables: `Hazard` and `Observation`. |
| `dedup.py` | "Is this the same hazard?" — bounding box pre-filter, then haversine. |
| `severity.py` | The 1–10 score. Replace this module to improve the scoring. |
| `hazard_service.py` | The lifecycle rules and status transitions. |
| `detector/` | The `Detector` interface plus mock and YOLO implementations. |
| `location.py` | Resolves coordinates from the request, EXIF, or the browser. |
| `routing.py` | Optional hazard-aware routing. |
| `demo.py` | Seed data and the scripted demo replay. |

---

## Setup

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Runs on <http://localhost:8000>. Interactive API docs at
<http://localhost:8000/docs>.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on <http://localhost:5173>. The Vite dev server proxies `/api` and
`/images` to the backend, so there is no CORS setup and nothing to configure.

---

## Running the demo

The backend starts empty. Two buttons in the dashboard header fill it:

**"Seed demo data"** — 10 hazards across real Manipal locations (Tiger Circle,
MIT main gate, End Point Road, …) with a realistic spread of types,
severities and statuses, including one awaiting repair proof and one already
verified.

**"Run demo story"** — replays the entire lifecycle on a fresh hazard in about
a second and prints every step, including a *failed* repair check. This is the
demo safety net: it needs no uploads, no GPS and no network.

Or from the command line:

```bash
curl -X POST localhost:8000/demo/seed
curl -X POST 'localhost:8000/demo/story?fail_first_repair=true'
curl -X POST localhost:8000/demo/reset
```

### Demo mode without a trained model

Mock detection is the **default**. It is deterministic — the same image always
gives the same answer — and it reads the filename as a hint:

| Filename contains | Detected as |
|---|---|
| `pothole`, `crater` | pothole |
| `manhole`, `drain` | manhole |
| `waterlog`, `flood`, `water` | waterlogging |
| `clean`, `repaired`, `fixed`, `smooth` | **nothing** (this is how a repair gets verified) |
| anything else | a stable pseudo-random result from the file's hash |

Generate a set of correctly-named sample photos:

```bash
python sample_data/generate_samples.py
```

---

## About GPS

**Live phone GPS is the most likely thing to fail during a demo.** Three
reasons, and they compound:

1. `navigator.geolocation` is **blocked on plain `http://` origins**. A phone
   hitting your laptop at `http://192.168.x.x:5173` gets nothing — only
   `localhost` and HTTPS are secure contexts.
2. Demo halls are **indoors**, so the fix degrades to wifi/cell triangulation
   with tens to hundreds of metres of error.
3. Uploaded photos usually have their **EXIF GPS stripped** (iOS strips it by
   default; anything sent through WhatsApp has none).

So RainGuard resolves location from three sources, in priority order:

1. **Explicit coordinates** — click the map in the dashboard. This is the
   default demo path and it always works.
2. **EXIF GPS** from the uploaded photo, if it survived.
3. **Browser geolocation**, if available — the dashboard tells you plainly
   when it is blocked instead of failing silently.

Every observation records which source it came from, shown in the observation
log. This is also just better engineering: a real field app needs manual
correction for poor signal.

If you *do* want to show live phone GPS, serve the dashboard through an HTTPS
tunnel (`ngrok`, `cloudflared`) and test it **at the venue, outdoors**, before
you present. Treat it as a bonus, never the spine of the demo.

---

## Plugging in a custom YOLO model

An off-the-shelf YOLO model detects **none** of RainGuard's classes — COCO has
no pothole, manhole or waterlogging class. You need trained weights.

```bash
pip install ultralytics
cp your_trained_weights.pt model/rainguard.pt
```

Then set `DETECTOR_MODE = "yolo"` in `backend/config.py`. If your class names
differ, map them in `CLASS_NAME_MAP` in `backend/detector/yolo_detector.py`.

Nothing else changes — `YoloDetector` implements the same `Detector` interface
as the mock. If the weights are missing, the backend logs a warning and falls
back to mock mode rather than crashing.

See `model/README.md` for training notes.

---

## Safe routing (optional)

```bash
pip install osmnx networkx scikit-learn
cd backend && python download_graph.py    # once, needs internet
```

This caches the Manipal street network to `model/manipal_graph.graphml`
(~3,000 nodes / ~7,000 edges). After that routing loads from disk in about a
second and **works offline**. Run it well before demo day.

The cost model:

```python
safe_cost(road) = length_metres + Σ (hazard.severity × 60)
```

for each open hazard within 30 m of that road. A severity-10 hazard makes a
road feel 600 m longer — enough to detour around on a dense grid, not enough
to send you across town. Penalties are applied in **both** directions of
travel, since a pothole blocks a road either way.

The **Safe routing** panel appears in the dashboard once the graph is cached,
and hides itself with an explanation otherwise. The core hazard workflow never
depends on it.

A route pair where the difference is visible: **Kunjibettu Junction → MIT Main
Gate** detours 184 m to avoid the severity-9.1 manhole.

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Detector mode and the thresholds currently in force. |
| `GET` | `/stats` | Counts by status and type, for the dashboard KPIs. |
| `POST` | `/detections` | Ingest an image. Multipart: `image`, `latitude`, `longitude`, optional `hazard_type` / `confidence` to bypass the detector. |
| `GET` | `/hazards` | All hazards. Filters: `status`, `type`, `min_severity`, `include_verified`. |
| `GET` | `/hazards/{id}` | One hazard plus its full observation log. |
| `POST` | `/hazards/{id}/repair` | Claim a repair → `REPAIR_PENDING`. |
| `POST` | `/hazards/{id}/verify` | Re-inspection. Multipart `image`, or `simulate=clean\|still_there` for a deterministic demo. |
| `POST` | `/hazards/{id}/reopen` | Undo a repair claim. |
| `GET` | `/hazards/near/{lat}/{lon}` | Hazards near a point. |
| `POST` | `/route` | Shortest vs hazard-avoiding route. |
| `GET` | `/route/status` | Whether routing is installed and the graph cached. |
| `POST` | `/demo/seed` · `/demo/story` · `/demo/reset` | Demo controls. |

Example:

```bash
curl -X POST localhost:8000/detections \
  -F "image=@sample_data/pothole_tiger_circle.jpg" \
  -F "latitude=13.3467" -F "longitude=74.7869"
```

---

## Demonstrating to SIH judges

A five-minute run that tells the whole story:

**1. Open the dashboard, click "Seed demo data".** (10 s)
> "This is Manipal. Ten hazards, colour-coded by risk — red is high, green is a
> verified repair. Marker size scales with severity."

**2. Click the map on an empty stretch of road, then upload
`sample_data/pothole_tiger_circle.jpg`.** (30 s)
> "A citizen reports a pothole. The detector classifies it and it lands on the
> map as SUSPECTED — one sighting isn't proof."

Pick somewhere with no seeded hazard nearby — around `13.3450, 74.7810` is
clear. The panel confirms the coordinates before you submit.

**3. Click a point a few metres away and upload `pothole_eshwar_nagar.jpg`.
Then do it once more.** (40 s)
> "Two more people photograph the *same* pothole. Notice we do **not** get
> extra markers — each merges as another observation, the severity rises, and
> on the third sighting it becomes CONFIRMED. This is the difference between
> RainGuard and a complaint inbox: 40 reports of one pothole is one hazard,
> not 40 tickets."

**4. With that hazard selected → "Mark as repaired".** (20 s)
> "The municipality says it's fixed. Status is REPAIR_PENDING — *not* closed.
> A claim isn't proof."

**5. Upload `pothole_tiger_circle.jpg` again as the re-inspection.** (20 s)
> "The re-inspection still shows the pothole. The check **fails** and the
> hazard reopens. You cannot close a hazard by asserting it."

**6. Mark repaired again, then upload the three `clean_road_*.jpg` files.** (40 s)
> "Three independent clean re-inspections. Now it's VERIFIED and drops off the
> active map. And here's the before/after pair — a human can see it's the same
> stretch of road, so we're not trusting the absence of a detection on its own."

**7. Safe routing panel: Kunjibettu Junction → MIT Main Gate.** (30 s)
> "Grey is the shortest route; green detours 184 m to avoid a severity-9.1 open
> manhole. The hazard map becomes routing input."

**8. If anything goes wrong, hit "Run demo story".** It replays all of the above
deterministically in one second, with narration for each step.

### Questions judges will ask

**"How do you know the repair photo is of the same place?"**
GPS plus a stored before/after pair a human can compare. The prototype is
AI-assisted and human-confirmed, not fully automatic — and we show you the
evidence rather than asking you to trust a missing detection.

**"What if two potholes are genuinely 5 m apart?"**
They merge, and we accept that. The 25 m radius is set by consumer GPS
accuracy (±5–15 m outdoors, worse under tree cover), not by pothole size. A
tighter radius would split repeat sightings of *one* pothole into several
hazards, which is the worse failure. It's one constant in `config.py`.

**"Is the model actually trained?"**
The prototype ships a deterministic mock detector so the full pipeline is
demonstrable today; the detector sits behind a one-method interface, and
swapping in trained YOLO weights is a config change. The interesting work —
deduplication, severity, verified repair — is model-independent.

**"Why not PostGIS / Kafka / microservices?"**
At this scale a bounding-box filter plus haversine over SQLite is exact and
instant. Reach for PostGIS when the data outgrows it, not before.

---

## Deploying (dashboard on Vercel, API on Render)

The dashboard is a static build and goes on Vercel happily. The API is **not**
deployed to Vercel, on purpose: it writes to a SQLite file and stores uploaded
images on disk, and Vercel Functions have an ephemeral filesystem, so both
would silently vanish between requests. Render gives it a normal disk and the
existing code runs unchanged.

### 1. API on Render

Push the repo to GitHub, then at <https://dashboard.render.com> choose
**New + → Blueprint** and select it. Render reads `render.yaml` and builds
`backend/` with no further configuration. Copy the resulting URL, e.g.
`https://rainguard-api.onrender.com`, and check `/health` responds.

**On the free plan the filesystem is ephemeral** — the database and uploaded
images are wiped when the service restarts or wakes from sleep. That is fine
for a demo: click **Seed demo data** and the map repopulates in a second. Add
a paid persistent disk mounted at `backend/storage` if you need it to survive.

Free instances also sleep after inactivity and take ~50 s to wake. **Load the
dashboard a few minutes before you present** so the API is warm.

### 2. Dashboard on Vercel

```bash
npm i -g vercel
cd frontend && vercel
```

Then set the API origin — without it the dashboard has no backend to call:

```bash
vercel env add VITE_API_BASE production   # paste your Render URL, no trailing slash
vercel --prod
```

Or set it under **Project → Settings → Environment Variables**. `VITE_API_BASE`
is read at *build* time, so redeploy after changing it.

### How the two modes differ

| | Local development | Deployed |
|---|---|---|
| `VITE_API_BASE` | unset | the Render URL |
| API calls | `/api/...` via the Vite dev proxy | absolute, to Render |
| Images | `/images/...` via the same proxy | absolute, via `assetUrl()` |
| CORS | not involved (one origin) | handled by `CORSMiddleware` |

Both paths are exercised by the same code in `src/api.js`; nothing is
dev-only except the proxy in `vite.config.js`.

### Routing in production

The safe-routing module stays **off** when deployed. Its dependencies
(osmnx, geopandas, scikit-learn) and the 10 MB street graph would blow past a
free instance's build time and memory. The panel detects this and explains
itself rather than erroring. Routing still works locally, which is where you
will demo it.

## Development notes

Built in the order: data model → API → dedup → severity → mock detection →
dashboard → repair workflow → routing. Each stage was tested before the next
began.

Deliberately **not** used: Docker, Kubernetes, authentication, cloud
deployment, microservices, Redis, PostGIS, event queues. Two processes, one
SQLite file.

To change behaviour, start in `backend/config.py`:

```python
DEDUP_RADIUS_METRES = 25.0              # how close counts as "the same hazard"
OBSERVATIONS_FOR_CONFIRMED = 3          # SUSPECTED -> CONFIRMED
CLEAN_OBSERVATIONS_FOR_VERIFIED = 3     # REPAIRED -> VERIFIED
DETECTOR_MODE = "mock"                  # or "yolo"
```
