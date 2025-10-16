# engine_core.py
# Backgammon core engine with SEPARATE bar/off indices per side:
# 0  = WHITE_BAR,   25 = WHITE_OFF
# 26 = BLACK_BAR,   27 = BLACK_OFF
# Board points 1..24 are the 24 triangles (WHITE moves 24→1, BLACK moves 1→24).

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Tuple, Optional, Iterable, Dict
import random
import copy





class Player(Enum):
    WHITE = auto()  # WHITE: 24 -> 1
    BLACK = auto()  # BLACK: 1 -> 24

def opponent(p: Player) -> Player:
    return Player.BLACK if p is Player.WHITE else Player.WHITE

@dataclass
class Move:
    start: int   # may be BAR index for the mover
    end: int     # may be OFF index for the mover
    die: int

@dataclass
class TurnRoute:
    moves: List[Move] = field(default_factory=list)

@dataclass
class Point:
    checkers: int = 0
    owner: Optional[Player] = None

    def add(self, owner: Player, n: int = 1) -> None:
        if self.owner is None:
            self.owner = owner
            self.checkers = n
        else:
            if self.owner != owner:
                raise ValueError("Cannot add to opponent-owned point without hit logic.")
            self.checkers += n

    def remove(self, n: int = 1) -> None:
        if self.checkers < n:
            raise ValueError("Not enough checkers to remove.")
        self.checkers -= n
        if self.checkers == 0:
            self.owner = None

@dataclass
class Board:
    # indices: 0..27  (28 pockets)
    points: List[Point] = field(default_factory=lambda: [Point() for _ in range(28)])

    def clone(self) -> "Board":
        return copy.deepcopy(self)

    # ── index helpers ──────────────────────────────────────────────────────────
    def bar_index(self, player: Player) -> int:
        return 0 if player is Player.WHITE else 26

    def off_index(self, player: Player) -> int:
        return 25 if player is Player.WHITE else 27

    def dir(self, player: Player) -> int:
        # movement along 24..1 in WHITE indexing for 1..24 pockets
        return -1 if player is Player.WHITE else +1

    def home_range(self, player: Player) -> range:
        return range(1, 7) if player is Player.WHITE else range(19, 25)

    # ── setup ─────────────────────────────────────────────────────────────────
    @staticmethod
    def standard_setup() -> "Board":
        b = Board()
        def put(idx: int, n: int, owner: Player) -> None:
            b.points[idx].add(owner, n)
        # WHITE
        put(24, 2, Player.WHITE)
        put(13, 5, Player.WHITE)
        put(8, 3, Player.WHITE)
        put(6, 5, Player.WHITE)
        # BLACK
        put(1, 2, Player.BLACK)
        put(12, 5, Player.BLACK)
        put(17, 3, Player.BLACK)
        put(19, 5, Player.BLACK)
        # (bars/offs start empty)
        return b

    # ── queries ───────────────────────────────────────────────────────────────
    def is_blocked_for(self, idx: int, player: Player) -> bool:
        if not (1 <= idx <= 24):  # bar/off never "blocked"
            return False
        pt = self.points[idx]
        return (pt.owner == opponent(player)) and (pt.checkers >= 2)

    def can_hit(self, idx: int, player: Player) -> bool:
        if not (1 <= idx <= 24):
            return False
        pt = self.points[idx]
        return (pt.owner == opponent(player)) and (pt.checkers == 1)

    def all_in_home(self, player: Player) -> bool:
        home = set(self.home_range(player))
        off = self.off_index(player)
        for i, pt in enumerate(self.points):
            if pt.owner == player:
                if i not in home and i != off:
                    return False
        return True

    def count_on_bar(self, player: Player) -> int:
        return self.points[self.bar_index(player)].checkers

    def count_off(self, player: Player) -> int:
        return self.points[self.off_index(player)].checkers

# ── dice ──────────────────────────────────────────────────────────────────────
def roll_dice() -> List[int]:
    a, b = random.randint(1, 6), random.randint(1, 6)
    return [a, b, a, b] if a == b else [a, b]

# ── move generation helpers ───────────────────────────────────────────────────
def legal_single_targets(board: Board, player: Player, start_idx: int, dice: Iterable[int]) -> List[Tuple[int, int]]:
    res: List[Tuple[int, int]] = []
    dice_list = list(dice)

    # If you have pieces on bar, you must enter from bar.
    if board.count_on_bar(player) > 0 and start_idx != board.bar_index(player):
        return res

    bar = board.bar_index(player)
    off = board.off_index(player)
    dir_ = board.dir(player)

    # From BAR: enter according to die
    if start_idx == bar:
        for d in dice_list:
            end = (25 - d) if player is Player.WHITE else d  # WHITE enters at 25-d, BLACK at d
            if 1 <= end <= 24 and not board.is_blocked_for(end, player):
                res.append((d, end))
        return res

    # From a board point
    if not (1 <= start_idx <= 24):
        return res
    if board.points[start_idx].owner != player or board.points[start_idx].checkers <= 0:
        return res

    for d in dice_list:
        end = start_idx + (dir_ * d)
        # Bearing off?
        if (player is Player.WHITE and end < 1) or (player is Player.BLACK and end > 24):
            if board.all_in_home(player):
                res.append((d, off))
            continue
        # Normal move
        if 1 <= end <= 24 and not board.is_blocked_for(end, player):
            res.append((d, end))

    return res

def apply_single_move(board: Board, player: Player, start: int, end: int) -> None:
    bar = board.bar_index(player)
    off = board.off_index(player)

    # remove one from the start
    board.points[start].remove(1)

    # bearing off
    if end == off:
        board.points[off].add(player, 1)
        return

    # handle hits
    if board.can_hit(end, player):
        opp = opponent(player)
        opp_bar = board.bar_index(opp)
        board.points[end].remove(1)
        board.points[opp_bar].add(opp, 1)

    # place on destination
    pt = board.points[end]
    if pt.owner is None or pt.owner == player:
        pt.add(player, 1)
    else:
        raise RuntimeError("Attempted to move onto a blocked point (should have been filtered).")

# Full-turn route generation (consumes all dice in every possible order)
def generate_all_routes(board: Board, player: Player, dice: List[int]) -> List[TurnRoute]:
    routes: List[TurnRoute] = []
    dice_list = dice[:]

    def backtrack(b: Board, remaining: List[int], acc: List[Move]) -> None:
        if not remaining:
            routes.append(TurnRoute(moves=acc[:]))
            return

        used_any = False
        used_mask = set()

        # Explore starts ( BAR first if any )
        starts = list(range(1,25))
        bar = b.bar_index(player)
        if b.count_on_bar(player) > 0:
            starts = [bar]

        for start in starts:
            # query legals from CURRENT board b
            cands = []
            for d in remaining:
                for die, end in legal_single_targets(b, player, start, [d]):
                    cands.append((die, end))

            for die, end in cands:
                key = (start, end, die, tuple(sorted(remaining)))
                if key in used_mask:
                    continue
                used_mask.add(key)

                b2 = b.clone()
                apply_single_move(b2, player, start, end)

                rem = remaining[:]
                rem.remove(die)
                used_any = True
                acc.append(Move(start=start, end=end, die=die))
                backtrack(b2, rem, acc)
                acc.pop()

        if not used_any:
            routes.append(TurnRoute(moves=acc[:]))

    backtrack(board, dice_list, [])
    # de-dup identical sequences
    uniq: Dict[Tuple[Tuple[int,int,int],...], TurnRoute] = {}
    for r in routes:
        k = tuple((m.start, m.end, m.die) for m in r.moves)
        uniq[k] = r
    return list(uniq.values())

# ── engine wrapper ────────────────────────────────────────────────────────────
class Engine:
    def __init__(self):
        self.board = Board.standard_setup()
        self.turn: Player = Player.WHITE
        self.dice: List[int] = []

    def new_game(self) -> None:
        self.board = Board.standard_setup()
        self.turn = Player.WHITE
        self.dice = []

    def roll(self) -> List[int]:
        self.dice = roll_dice()
        return self.dice

    def legal_targets_from(self, start_idx: int) -> List[Tuple[int, int]]:
        return legal_single_targets(self.board, self.turn, start_idx, self.dice)

    def generate_routes(self) -> List[TurnRoute]:
        return generate_all_routes(self.board, self.turn, self.dice)

    def apply_route(self, route: TurnRoute) -> None:
        for m in route.moves:
            apply_single_move(self.board, self.turn, m.start, m.end)
            try:
                self.dice.remove(m.die)
            except ValueError:
                pass

    def end_turn(self) -> None:
        self.turn = opponent(self.turn)
        self.dice = []

    def has_won(self, p: Player) -> bool:
        return self.board.count_off(p) >= 15
