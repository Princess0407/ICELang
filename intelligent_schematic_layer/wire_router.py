import heapq

GRID_SIZE  = 500
GRID_SCALE = 10


def world_to_grid(x: float, y: float) -> tuple:
    col = int(round(x * GRID_SCALE)) + GRID_SIZE // 2
    row = int(round(y * GRID_SCALE)) + GRID_SIZE // 2
    col = max(0, min(GRID_SIZE - 1, col))
    row = max(0, min(GRID_SIZE - 1, row))
    return col, row


def grid_to_world(col: int, row: int) -> tuple:
    x = (col - GRID_SIZE // 2) / GRID_SCALE
    y = (row - GRID_SIZE // 2) / GRID_SCALE
    return round(x, 4), round(y, 4)


def astar(grid: list, start: tuple, goal: tuple) -> list:
    if start == goal:
        return [start]

    def heuristic(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    open_set  = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score   = {start: 0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            return list(reversed(path))

        col, row = current
        for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nb  = (col + dc, row + dr)
            nc, nr = nb
            if not (0 <= nc < GRID_SIZE and 0 <= nr < GRID_SIZE):
                continue
            if grid[nr][nc]:
                continue
            new_g = g_score[current] + 1
            if new_g < g_score.get(nb, float("inf")):
                came_from[nb] = current
                g_score[nb]   = new_g
                f = new_g + heuristic(nb, goal)
                heapq.heappush(open_set, (f, nb))

    return []


def path_to_segments(path: list) -> list:
    if len(path) < 2:
        return []
    segments  = []
    seg_start = grid_to_world(*path[0])
    for i in range(1, len(path)):
        if i == len(path) - 1:
            segments.append((seg_start, grid_to_world(*path[i])))
        else:
            prev_dir = (path[i][0]-path[i-1][0], path[i][1]-path[i-1][1])
            next_dir = (path[i+1][0]-path[i][0], path[i+1][1]-path[i][1])
            if prev_dir != next_dir:
                segments.append((seg_start, grid_to_world(*path[i])))
                seg_start = grid_to_world(*path[i])
    return segments


def find_junctions(all_paths: list) -> list:
    from collections import Counter
    all_points = []
    for path in all_paths:
        all_points.extend(path)
    counts = Counter(all_points)
    return [pt for pt, count in counts.items() if count >= 3]


def route(placed: dict, edges: list) -> dict:
    # start with a completely empty grid — nothing blocked
    grid      = [[False] * GRID_SIZE for _ in range(GRID_SIZE)]
    results   = {}
    all_paths = []

    for node1, node2, label in edges:
        if node1 not in placed or node2 not in placed:
            continue

        start = world_to_grid(*placed[node1])
        goal  = world_to_grid(*placed[node2])

        print(f"  routing {node1}{start} → {node2}{goal}")

        path = astar(grid, start, goal)

        if path:
            # block middle of routed path so next wire routes around it
            for pt in path[1:-1]:
                c, r = pt
                grid[r][c] = True

            segments   = path_to_segments(path)
            world_path = [grid_to_world(*pt) for pt in path]
            all_paths.append(world_path)

            results[label] = {
                "from":     node1,
                "to":       node2,
                "segments": segments,
                "points":   world_path
            }
        else:
            results[label] = {
                "from":     node1,
                "to":       node2,
                "segments": [],
                "points":   [],
                "error":    "no path found"
            }

    junctions = find_junctions(all_paths)
    return {"wires": results, "junctions": junctions}
