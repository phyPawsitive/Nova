# Welcome to
# __________         __    __  .__                               __
# \______   \_____ _/  |__/  |_|  |   ____   ______ ____ _____  |  | __ ____
#  |    |  _/\__  \\   __\   __\  | _/ __ \ /  ___//    \\__  \ |  |/ // __ \
#  |    |   \ / __ \|  |  |  | |  |_\  ___/ \___ \|   |  \/ __ \|    <\  ___/
#  |________/(______/__|  |__| |____/\_____>______>___|__(______/__|__\\_____>
#
# This file can be a nice home for your Battlesnake logic and helper functions.
#
# To get you started we've included code to prevent your Battlesnake from moving backwards.
# For more info see docs.battlesnake.com

import random
import typing
from collections import deque

Coord = typing.Tuple[int, int]

DIRECTIONS: typing.Dict[str, Coord] = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}


# info is called when you create your Battlesnake on play.battlesnake.com
# and controls your Battlesnake's appearance
# TIP: If you open your Battlesnake URL in a browser you should see this data
def info() -> typing.Dict:
    print("INFO")

    return {
        "apiversion": "1",
        "author": "phypawsitive",  # TODO: Your Battlesnake Username
        "color": "#0D0D0D ",  # TODO: Choose color
        "head": "silly",  # TODO: Choose head
        "tail": "freckled",  # TODO: Choose tail
    }


# start is called when your Battlesnake begins a game
def start(game_state: typing.Dict):
    print("GAME START")


# end is called when your Battlesnake finishes a game
def end(game_state: typing.Dict):
    print("GAME OVER\n")


def _body_coords(snake: typing.Dict) -> typing.List[Coord]:
    return [(seg["x"], seg["y"]) for seg in snake["body"]]


def _just_ate(snake: typing.Dict) -> bool:
    # A snake that ate this turn keeps its tail segment duplicated for one
    # turn instead of vacating it, since its body grew instead of shifting.
    body = snake["body"]
    return len(body) > 1 and body[-1] == body[-2]


def _blocked_cells(board: typing.Dict) -> typing.Set[Coord]:
    """Cells that will still be occupied by a snake body next turn.

    Every snake's tail vacates as it moves forward, unless that snake just
    ate and its body didn't shrink, so tails are excluded except then.
    """
    blocked: typing.Set[Coord] = set()
    for snake in board["snakes"]:
        body = _body_coords(snake)
        segments = body if _just_ate(snake) else body[:-1]
        blocked.update(segments)
    return blocked


def _in_bounds(cell: Coord, width: int, height: int) -> bool:
    x, y = cell
    return 0 <= x < width and 0 <= y < height


def _neighbors(cell: Coord) -> typing.Iterator[Coord]:
    x, y = cell
    yield (x, y + 1)
    yield (x, y - 1)
    yield (x - 1, y)
    yield (x + 1, y)


def _flood_fill_size(
    start_cell: Coord, blocked: typing.Set[Coord], width: int, height: int, cap: int
) -> int:
    """Count reachable free cells from start_cell, capped for speed.

    Used only to detect "is this move a dead end smaller than my own body",
    so we don't need to search past that threshold.
    """
    if not _in_bounds(start_cell, width, height) or start_cell in blocked:
        return 0
    seen = {start_cell}
    queue = deque([start_cell])
    while queue and len(seen) < cap:
        cell = queue.popleft()
        for neighbor in _neighbors(cell):
            if neighbor in seen or neighbor in blocked:
                continue
            if not _in_bounds(neighbor, width, height):
                continue
            seen.add(neighbor)
            queue.append(neighbor)
    return len(seen)


def _bfs_distances(
    start_cell: Coord, blocked: typing.Set[Coord], width: int, height: int
) -> typing.Dict[Coord, int]:
    dist = {start_cell: 0}
    queue = deque([start_cell])
    while queue:
        cell = queue.popleft()
        for neighbor in _neighbors(cell):
            if neighbor in dist or neighbor in blocked:
                continue
            if not _in_bounds(neighbor, width, height):
                continue
            dist[neighbor] = dist[cell] + 1
            queue.append(neighbor)
    return dist


def _territory_score(candidate_head: Coord, board: typing.Dict, my_id: str) -> int:
    """Contested-territory (Voronoi) score for moving our head to candidate_head.

    Run a BFS from every snake's head at once and award each empty cell to
    whichever snake reaches it first; distance ties go to the longer snake
    (it wins a head-on collision there), and ties between equal-length
    snakes are left unclaimed.

    This is the direct counter to opponents like Battlesnake-rs's "Hovering
    Hobbs", which scores territory with a flood fill from its own head only.
    That kind of score never checks whether another snake can reach the same
    square just as fast, so it happily "claims" contested cells. Scoring on
    who actually wins the race for each cell lets us cut off space Hobbs
    assumes is already its own, instead of just fleeing toward open area.
    """
    width, height = board["width"], board["height"]
    blocked = _blocked_cells(board)
    # Wall off our hypothetical new head so other snakes' BFS can't route
    # through it, while still letting our own BFS start from that cell.
    blocked.add(candidate_head)

    lengths = {snake["id"]: len(snake["body"]) for snake in board["snakes"]}
    distances: typing.Dict[str, typing.Dict[Coord, int]] = {}
    for snake in board["snakes"]:
        sid = snake["id"]
        head = candidate_head if sid == my_id else (snake["body"][0]["x"], snake["body"][0]["y"])
        distances[sid] = _bfs_distances(head, blocked, width, height)

    score = 0
    for x in range(width):
        for y in range(height):
            cell = (x, y)
            best_sid = None
            best_dist = None
            contested = False
            for sid, dist in distances.items():
                d = dist.get(cell)
                if d is None:
                    continue
                if best_dist is None or d < best_dist:
                    best_dist, best_sid, contested = d, sid, False
                elif d == best_dist:
                    if lengths[sid] > lengths[best_sid]:
                        best_sid, contested = sid, False
                    elif lengths[sid] == lengths[best_sid]:
                        contested = True
            if contested or best_sid is None:
                continue  # no-man's-land: worth nothing to either side
            score += 1 if best_sid == my_id else -1
    return score


def _nearest_food_distance(
    head: Coord, board: typing.Dict, blocked: typing.Set[Coord]
) -> typing.Optional[int]:
    food = [(f["x"], f["y"]) for f in board["food"]]
    if not food:
        return None
    dist = _bfs_distances(head, blocked, board["width"], board["height"])
    reachable = [dist[f] for f in food if f in dist]
    return min(reachable) if reachable else None


# move is called on every turn and returns your next move
# Valid moves are "up", "down", "left", or "right"
# See https://docs.battlesnake.com/api/example-move for available data
def move(game_state: typing.Dict) -> typing.Dict:
    you = game_state["you"]
    board = game_state["board"]
    width, height = board["width"], board["height"]

    my_id = you["id"]
    my_head = (you["body"][0]["x"], you["body"][0]["y"])
    my_length = len(you["body"])
    my_health = you["health"]

    blocked = _blocked_cells(board)

    opponents = [s for s in board["snakes"] if s["id"] != my_id]
    opponent_heads = {(s["body"][0]["x"], s["body"][0]["y"]): len(s["body"]) for s in opponents}

    # Hard filter: walls, snake bodies, and our own neck are guaranteed
    # death, never worth considering.
    safe_moves = []
    for direction, (dx, dy) in DIRECTIONS.items():
        cell = (my_head[0] + dx, my_head[1] + dy)
        if not _in_bounds(cell, width, height):
            continue
        if cell in blocked:
            continue
        safe_moves.append((direction, cell))

    if not safe_moves:
        print(f"MOVE {game_state['turn']}: No safe moves detected! Moving down")
        return {"move": "down"}

    scored_moves = []
    for direction, cell in safe_moves:
        score = 0.0

        # Soft filter: a cell next to an opponent's head is only a guaranteed
        # loss if they're equal or longer (equal length still kills us both).
        # Against a shorter opponent, the same square is bait -- we win the
        # head-to-head, so reward it instead.
        risky = False
        for ohead, olen in opponent_heads.items():
            if cell in set(_neighbors(ohead)):
                if olen >= my_length:
                    risky = True
                else:
                    score += 5
        if risky:
            score -= 1000

        # Don't walk into a pocket smaller than our own body, no matter how
        # much open board it looks like it leads to right now.
        space = _flood_fill_size(cell, blocked, width, height, cap=my_length * 2 + 5)
        if space < my_length:
            score -= 500 * (my_length - space)

        # Core counter-strategy: fight for contested territory (Voronoi)
        # rather than just maximizing our own reachable area.
        score += 2 * _territory_score(cell, board, my_id)

        # Only chase food once health matters; otherwise keep prioritizing
        # board control, since Hobbs-style bots lean on space, not hunger.
        if my_health < 50:
            food_dist = _nearest_food_distance(cell, board, blocked)
            if food_dist is not None:
                score += max(0, 20 - food_dist)

        scored_moves.append((score, direction))

    scored_moves.sort(key=lambda t: t[0], reverse=True)
    best_score = scored_moves[0][0]
    best_moves = [d for s, d in scored_moves if s == best_score]
    chosen = random.choice(best_moves)

    print(f"MOVE {game_state['turn']}: {chosen} (score={best_score})")
    return {"move": chosen}


# Start server when `python main.py` is run
if __name__ == "__main__":
    from server import run_server

    run_server({"info": info, "start": start, "move": move, "end": end})
