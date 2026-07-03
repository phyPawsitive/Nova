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

import time
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


# --- Lookahead search -------------------------------------------------------
#
# Everything above this line scores a single position. Everything below runs
# Minimax with alpha-beta pruning (iterative deepening, time-boxed to the
# game's move timeout) on top of that scoring, so moves account for how the
# territory fight actually plays out a few rounds ahead instead of assuming
# opponents freeze in place. Search is "Paranoid": every opponent is treated
# as a single adversary picking its worst-case combined move against us,
# which is the standard simplification of N-player Minimax (the alternative,
# MaxN, has each opponent selfishly optimize for itself instead).
#
# To keep branching bounded when more than two snakes are alive, only the
# two nearest opponents are simulated as active adversaries; farther-away
# snakes are held in place turn-by-turn (still blocking cells, just not
# considered as an active threat) rather than fully game-tree-searched.

TIME_BUDGET_FLOOR_SECONDS = 0.05
TIME_BUDGET_SAFETY_MARGIN_SECONDS = 0.15
MAX_ACTIVE_OPPONENTS = 2
MAX_SEARCH_ROUNDS = 12


class _TimeUp(Exception):
    pass


def _build_sim_state(board: typing.Dict) -> typing.Dict:
    return {
        "width": board["width"],
        "height": board["height"],
        "food": {(f["x"], f["y"]) for f in board["food"]},
        "snakes": {
            snake["id"]: {
                "body": _body_coords(snake),
                "health": snake["health"],
                "alive": True,
            }
            for snake in board["snakes"]
        },
    }


def _sim_state_to_board(sim_state: typing.Dict) -> typing.Dict:
    return {
        "width": sim_state["width"],
        "height": sim_state["height"],
        "food": [{"x": x, "y": y} for x, y in sim_state["food"]],
        "snakes": [
            {"id": sid, "body": [{"x": x, "y": y} for x, y in snake["body"]]}
            for sid, snake in sim_state["snakes"].items()
            if snake["alive"]
        ],
    }


def _legal_moves_for(sim_state: typing.Dict, snake_id: str) -> typing.List[str]:
    head = sim_state["snakes"][snake_id]["body"][0]
    width, height = sim_state["width"], sim_state["height"]
    moves = [
        direction
        for direction, (dx, dy) in DIRECTIONS.items()
        if _in_bounds((head[0] + dx, head[1] + dy), width, height)
    ]
    return moves or ["up"]  # boxed in on all sides; must still return something


def _apply_moves(
    sim_state: typing.Dict, moves: typing.Dict[str, Coord], frozen_ids: typing.FrozenSet[str]
) -> typing.Dict:
    """Advance every snake one turn given its chosen (dx, dy), then resolve
    eliminations (walls, starvation, body collisions, head-to-heads) the way
    the Battlesnake rules engine does. Frozen or already-dead snakes are
    copied through unchanged, acting as static obstacles for this round.
    """
    width, height = sim_state["width"], sim_state["height"]
    new_snakes: typing.Dict[str, typing.Dict] = {}
    new_heads: typing.Dict[str, Coord] = {}

    for sid, snake in sim_state["snakes"].items():
        if not snake["alive"] or sid in frozen_ids:
            new_snakes[sid] = snake
            continue
        dx, dy = moves[sid]
        head = snake["body"][0]
        new_head = (head[0] + dx, head[1] + dy)
        ate = new_head in sim_state["food"]
        new_body = [new_head] + (snake["body"] if ate else snake["body"][:-1])
        new_snakes[sid] = {
            "body": new_body,
            "health": 100 if ate else snake["health"] - 1,
            "alive": True,
        }
        new_heads[sid] = new_head

    eaten = {new_snakes[sid]["body"][0] for sid in new_heads if new_snakes[sid]["body"][0] in sim_state["food"]}
    new_food = sim_state["food"] - eaten

    for sid, head in new_heads.items():
        snake = new_snakes[sid]
        if not _in_bounds(head, width, height) or snake["health"] <= 0:
            snake["alive"] = False
            continue
        if any(head in other["body"][1:] for other in new_snakes.values()):
            snake["alive"] = False
            continue
        for other_sid, other in new_snakes.items():
            if other_sid != sid and other["body"][0] == head:
                if len(other["body"]) >= len(snake["body"]):
                    snake["alive"] = False
                break

    return {"width": width, "height": height, "food": new_food, "snakes": new_snakes}


def _evaluate(sim_state: typing.Dict, my_id: str) -> float:
    snake = sim_state["snakes"].get(my_id)
    if snake is None or not snake["alive"]:
        return -100000.0

    opponents_alive = [s for sid, s in sim_state["snakes"].items() if sid != my_id and s["alive"]]
    if not opponents_alive:
        return 100000.0

    board = _sim_state_to_board(sim_state)
    my_head = snake["body"][0]
    my_length = len(snake["body"])

    score = 2 * _territory_score(my_head, board, my_id)

    blocked = _blocked_cells(board)
    blocked.discard(my_head)
    space = _flood_fill_size(my_head, blocked, sim_state["width"], sim_state["height"], cap=my_length * 2 + 5)
    if space < my_length:
        score -= 500 * (my_length - space)

    if snake["health"] < 50:
        food_dist = _nearest_food_distance(my_head, board, blocked)
        if food_dist is not None:
            score += max(0, 20 - food_dist)

    score += 0.5 * my_length
    return score


def _paranoid_search(
    sim_state: typing.Dict,
    my_id: str,
    active_agents: typing.List[str],
    frozen_ids: typing.FrozenSet[str],
    depth: int,
    alpha: float,
    beta: float,
    moves_so_far: typing.Dict[str, Coord],
    agent_idx: int,
    deadline: float,
) -> float:
    """One round of Paranoid Minimax: every agent in active_agents (us first,
    then each active opponent) picks a move maximizing (us) or minimizing
    (them) the eventual score, in turn, against the same pre-round state.
    Once everyone has chosen, the round is applied and we recurse.
    """
    if time.perf_counter() > deadline:
        raise _TimeUp()

    if agent_idx == len(active_agents):
        next_state = _apply_moves(sim_state, moves_so_far, frozen_ids)
        return _minimax_round(next_state, my_id, active_agents, frozen_ids, depth - 1, alpha, beta, deadline)

    agent_id = active_agents[agent_idx]
    snake = sim_state["snakes"][agent_id]
    if not snake["alive"]:
        return _paranoid_search(
            sim_state, my_id, active_agents, frozen_ids, depth, alpha, beta, moves_so_far, agent_idx + 1, deadline
        )

    maximizing = agent_id == my_id
    best = float("-inf") if maximizing else float("inf")
    for direction in _legal_moves_for(sim_state, agent_id):
        moves_so_far[agent_id] = DIRECTIONS[direction]
        value = _paranoid_search(
            sim_state, my_id, active_agents, frozen_ids, depth, alpha, beta, moves_so_far, agent_idx + 1, deadline
        )
        if maximizing:
            best = max(best, value)
            alpha = max(alpha, best)
        else:
            best = min(best, value)
            beta = min(beta, best)
        if alpha >= beta:
            break
    return best


def _minimax_round(
    sim_state: typing.Dict,
    my_id: str,
    active_agents: typing.List[str],
    frozen_ids: typing.FrozenSet[str],
    depth: int,
    alpha: float,
    beta: float,
    deadline: float,
) -> float:
    my_snake = sim_state["snakes"].get(my_id)
    if my_snake is None or not my_snake["alive"] or depth <= 0:
        return _evaluate(sim_state, my_id)
    if not any(sim_state["snakes"][a]["alive"] for a in active_agents if a != my_id):
        return _evaluate(sim_state, my_id)
    return _paranoid_search(sim_state, my_id, active_agents, frozen_ids, depth, alpha, beta, {}, 0, deadline)


def _choose_active_agents(sim_state: typing.Dict, my_id: str) -> typing.Tuple[typing.List[str], typing.FrozenSet[str]]:
    my_head = sim_state["snakes"][my_id]["body"][0]
    living_opponents = [sid for sid, s in sim_state["snakes"].items() if sid != my_id and s["alive"]]
    living_opponents.sort(
        key=lambda sid: abs(sim_state["snakes"][sid]["body"][0][0] - my_head[0])
        + abs(sim_state["snakes"][sid]["body"][0][1] - my_head[1])
    )
    active = living_opponents[:MAX_ACTIVE_OPPONENTS]
    frozen = frozenset(living_opponents[MAX_ACTIVE_OPPONENTS:])
    return [my_id] + active, frozen


def _search_best_move(sim_state: typing.Dict, my_id: str, deadline: float) -> typing.Tuple[typing.Optional[str], float]:
    active_agents, frozen_ids = _choose_active_agents(sim_state, my_id)

    best_direction = None
    best_score = float("-inf")
    depth = 1
    while True:
        try:
            alpha, beta = float("-inf"), float("inf")
            round_best_direction, round_best_score = None, float("-inf")
            for direction in _legal_moves_for(sim_state, my_id):
                moves = {my_id: DIRECTIONS[direction]}
                value = _paranoid_search(
                    sim_state, my_id, active_agents, frozen_ids, depth, alpha, beta, moves, 1, deadline
                )
                if value > round_best_score:
                    round_best_score, round_best_direction = value, direction
                alpha = max(alpha, round_best_score)
        except _TimeUp:
            break

        best_direction, best_score = round_best_direction, round_best_score
        depth += 1
        if depth > MAX_SEARCH_ROUNDS or time.perf_counter() > deadline:
            break

    return best_direction, best_score


# move is called on every turn and returns your next move
# Valid moves are "up", "down", "left", or "right"
# See https://docs.battlesnake.com/api/example-move for available data
def move(game_state: typing.Dict) -> typing.Dict:
    board = game_state["board"]
    my_id = game_state["you"]["id"]

    timeout_ms = game_state.get("game", {}).get("timeout", 500)
    time_budget = max(TIME_BUDGET_FLOOR_SECONDS, timeout_ms / 1000.0 - TIME_BUDGET_SAFETY_MARGIN_SECONDS)
    deadline = time.perf_counter() + time_budget

    sim_state = _build_sim_state(board)
    chosen, score = _search_best_move(sim_state, my_id, deadline)

    if chosen is None:
        print(f"MOVE {game_state['turn']}: No safe moves detected! Moving down")
        return {"move": "down"}

    print(f"MOVE {game_state['turn']}: {chosen} (score={score})")
    return {"move": chosen}


# Start server when `python main.py` is run
if __name__ == "__main__":
    from server import run_server

    run_server({"info": info, "start": start, "move": move, "end": end})
