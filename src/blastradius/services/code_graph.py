from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass
class GraphEdge:
    src: str
    dst: str
    edge_type: str
    reason: str = ""


@dataclass
class BlastRadiusGraph:
    nodes: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)


def service_name_for_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if normalized.startswith("services/"):
        parts = normalized.split("/")
        if len(parts) >= 2:
            return parts[1]
    if normalized.startswith("packages/"):
        parts = normalized.split("/")
        if len(parts) >= 2:
            return parts[1]  # common
    return None


def count_importers(import_edges: Iterable[tuple[str, str]], target_path: str) -> int:
    """Fan-out = number of edges where dst == target (importers of target)."""
    return sum(1 for src, dst in import_edges if dst == target_path)


class CodeGraph:
    """In-memory import graph. Edge direction: src imports dst."""

    def __init__(self, import_edges: list[tuple[str, str]], path_to_service: dict[str, str | None]):
        self.path_to_service = path_to_service
        # reverse: dst → set(src)  (importers of dst)
        self.importers: dict[str, set[str]] = defaultdict(set)
        # outbound: src → set(dst)
        self.imports: dict[str, set[str]] = defaultdict(set)
        for src, dst in import_edges:
            self.importers[dst].add(src)
            self.imports[src].add(dst)

    def importer_count(self, path: str) -> int:
        return len(self.importers.get(path, set()))

    def expand_blast_radius(
        self,
        seed_paths: list[str],
        *,
        depth: int = 2,
        cap: int = 50,
    ) -> BlastRadiusGraph:
        seeds = list(dict.fromkeys(seed_paths))
        file_nodes: set[str] = set(seeds)
        service_nodes: set[str] = set()

        for seed in seeds:
            svc = self.path_to_service.get(seed) or service_name_for_path(seed)
            if svc:
                service_nodes.add(svc)

        # Aggressive fan-out: any packages/ seed includes ALL importers.
        for seed in seeds:
            if seed.startswith("packages/"):
                file_nodes.update(self.importers.get(seed, set()))

        # BFS primarily on reverse imports (importers).
        queue: deque[tuple[str, int]] = deque((s, 0) for s in seeds)
        visited: set[str] = set(seeds)
        while queue and len(file_nodes) < cap:
            node, d = queue.popleft()
            if d >= depth:
                continue
            # reverse imports
            for importer in sorted(self.importers.get(node, set())):
                if importer not in visited:
                    visited.add(importer)
                    file_nodes.add(importer)
                    queue.append((importer, d + 1))
                    if len(file_nodes) >= cap:
                        break
            # optional outbound at depth 1 for context
            if d == 0:
                for imported in sorted(self.imports.get(node, set())):
                    if imported not in visited:
                        visited.add(imported)
                        file_nodes.add(imported)
                        # do not expand further outbound beyond context
                        if len(file_nodes) >= cap:
                            break

        for path in list(file_nodes):
            svc = self.path_to_service.get(path) or service_name_for_path(path)
            if svc:
                service_nodes.add(svc)

        # Trim files if over cap (services are virtual and extra).
        ordered_files = sorted(file_nodes)
        if len(ordered_files) > cap:
            # Keep seeds first.
            seed_set = set(seeds)
            rest = [p for p in ordered_files if p not in seed_set]
            ordered_files = list(seeds) + rest
            ordered_files = ordered_files[:cap]
            file_nodes = set(ordered_files)

        nodes: list[dict] = []
        for path in sorted(file_nodes):
            nodes.append(
                {
                    "id": f"file:{path}",
                    "type": "file",
                    "label": path.rsplit("/", 1)[-1],
                    "path": path,
                }
            )
        for svc in sorted(service_nodes):
            nodes.append({"id": f"svc:{svc}", "type": "service", "label": svc})

        edges: list[dict] = []
        # virtual belongs_to
        for path in sorted(file_nodes):
            svc = self.path_to_service.get(path) or service_name_for_path(path)
            if svc and svc in service_nodes:
                edges.append(
                    {
                        "from": f"file:{path}",
                        "to": f"svc:{svc}",
                        "reason": "belongs_to",
                    }
                )
        # import edges among included files
        for src in sorted(file_nodes):
            for dst in sorted(self.imports.get(src, set())):
                if dst in file_nodes:
                    edges.append(
                        {
                            "from": f"file:{src}",
                            "to": f"file:{dst}",
                            "reason": "imports",
                        }
                    )

        return BlastRadiusGraph(nodes=nodes, edges=edges)
