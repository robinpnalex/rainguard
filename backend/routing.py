"""
Optional: safer routing around high-severity hazards.

    safe_cost(edge) = length_metres + hazard_penalty(edge)

An edge picks up a penalty for every open hazard within HAZARD_EDGE_RADIUS_M
of it, scaled by that hazard's severity. Routing on `length` gives the
shortest path; routing on `safe_cost` gives a path that will detour around a
bad stretch of road if the detour is short enough to be worth it.

This module is deliberately isolated. If osmnx/networkx are not installed the
rest of NIRVANA runs exactly as before -- the /route endpoints just report
that routing is unavailable.

First call downloads the Manipal street network from OpenStreetMap and caches
it to model/manipal_graph.graphml. Do that once, before demo day: the
download needs internet and takes a minute or two. After that it loads from
disk in about a second and works offline.
"""
from pathlib import Path

from config import BASE_DIR, MANIPAL_CENTRE

GRAPH_PATH = BASE_DIR.parent / "model" / "manipal_graph.graphml"
GRAPH_RADIUS_M = 4000  # how much of Manipal to download

# A hazard influences edges within this distance of it.
HAZARD_EDGE_RADIUS_M = 30.0
# Metres of "virtual detour" added per severity point. 60 means a severity
# 10 hazard makes an edge feel 600 m longer, which is enough to route around
# it on a dense street grid but not enough to send you across town.
PENALTY_METRES_PER_SEVERITY = 60.0

_graph = None


class RoutingUnavailable(RuntimeError):
    pass


def available() -> bool:
    try:
        import networkx  # noqa: F401
        import osmnx  # noqa: F401
        return True
    except ImportError:
        return False


def load_graph(force_download: bool = False):
    """Load the cached street graph, downloading it once if needed."""
    global _graph
    if _graph is not None and not force_download:
        return _graph
    if not available():
        raise RoutingUnavailable(
            "osmnx and networkx are not installed. "
            "Run: pip install osmnx networkx"
        )

    import osmnx as ox

    if GRAPH_PATH.exists() and not force_download:
        _graph = ox.load_graphml(GRAPH_PATH)
    else:
        GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
        _graph = ox.graph_from_point(
            MANIPAL_CENTRE, dist=GRAPH_RADIUS_M, network_type="drive"
        )
        ox.save_graphml(_graph, GRAPH_PATH)
    return _graph


def build_safe_costs(graph, hazards) -> dict:
    """
    Annotate every edge with `safe_cost` and return per-edge hazard debug info.

    `hazards` is a list of objects with .latitude, .longitude, .severity, .id.
    """
    import osmnx as ox

    from geo import distance_metres

    # Reset, so repeated calls do not accumulate penalties.
    for _, _, data in graph.edges(data=True):
        data["safe_cost"] = float(data.get("length", 1.0))
        data["hazards"] = []

    if not hazards:
        return {}

    lats = [h.latitude for h in hazards]
    lons = [h.longitude for h in hazards]
    # Snap each hazard to its nearest street segment.
    nearest = ox.nearest_edges(graph, X=lons, Y=lats, return_dist=True)
    edges, distances = nearest

    penalised: dict = {}
    for hazard, edge, dist in zip(hazards, edges, distances):
        if dist > HAZARD_EDGE_RADIUS_M:
            continue  # too far from any road to be trusted
        u, v, _key = edge
        penalty = hazard.severity * PENALTY_METRES_PER_SEVERITY

        # A pothole blocks the road in BOTH directions. The graph is a
        # MultiDiGraph, so u->v and v->u are separate edge objects and the
        # reverse one would otherwise keep its unpenalised cost -- which
        # silently made half of all journeys ignore the hazard.
        for a, b in ((u, v), (v, u)):
            if not graph.has_edge(a, b):
                continue
            for key, data in graph[a][b].items():
                data["safe_cost"] = (
                    data.get("safe_cost", data.get("length", 1.0)) + penalty
                )
                data["hazards"].append(hazard.id)
                penalised.setdefault((a, b, key), []).append(
                    {
                        "hazard_id": hazard.id,
                        "severity": hazard.severity,
                        "penalty_m": penalty,
                    }
                )
    return penalised


def route(start: tuple[float, float], end: tuple[float, float], hazards) -> dict:
    """Return the shortest route and the hazard-avoiding route between two points."""
    import networkx as nx
    import osmnx as ox

    graph = load_graph()
    build_safe_costs(graph, hazards)

    origin = ox.nearest_nodes(graph, X=start[1], Y=start[0])
    destination = ox.nearest_nodes(graph, X=end[1], Y=end[0])

    def path_for(weight: str) -> dict:
        nodes = nx.shortest_path(graph, origin, destination, weight=weight)
        length, hazard_ids = 0.0, set()
        for a, b in zip(nodes, nodes[1:]):
            # Pick the parallel edge the router itself would have taken --
            # i.e. the cheapest by the same weight it optimised for.
            data = min(
                graph[a][b].values(),
                key=lambda d: d.get(weight, d.get("length", 1.0)),
            )
            length += float(data.get("length", 0.0))
            hazard_ids.update(data.get("hazards", []))
        coords = [[graph.nodes[n]["y"], graph.nodes[n]["x"]] for n in nodes]
        return {
            "coordinates": coords,
            "distance_metres": round(length, 1),
            "hazard_ids": sorted(hazard_ids),
            "hazard_count": len(hazard_ids),
        }

    shortest = path_for("length")
    safest = path_for("safe_cost")
    return {
        "shortest": shortest,
        "safest": safest,
        "detour_metres": round(safest["distance_metres"] - shortest["distance_metres"], 1),
        "hazards_avoided": shortest["hazard_count"] - safest["hazard_count"],
    }
