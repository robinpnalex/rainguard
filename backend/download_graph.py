#!/usr/bin/env python3
"""
Pre-download the Manipal street network for the safe-routing demo.

    python download_graph.py

Run this ONCE, on a good connection, well before demo day. It caches the
graph to model/manipal_graph.graphml; after that routing loads from disk in
about a second and needs no internet at all.
"""
import routing


def main() -> None:
    if not routing.available():
        raise SystemExit("Install routing deps first:  pip install osmnx networkx")

    print(f"Downloading {routing.GRAPH_RADIUS_M} m of drivable roads around Manipal...")
    graph = routing.load_graph(force_download=True)
    print(f"  nodes: {graph.number_of_nodes()}")
    print(f"  edges: {graph.number_of_edges()}")
    print(f"  cached to: {routing.GRAPH_PATH}")


if __name__ == "__main__":
    main()
