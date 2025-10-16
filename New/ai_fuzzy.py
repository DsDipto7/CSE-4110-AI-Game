# ai_fuzzy.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
import copy

from engine_core import Engine, Board, Player, Move, TurnRoute, opponent

def pip_count(board: Board, p: Player) -> int:
    pip = 0
    for i, pt in enumerate(board.points):
        if pt.owner == p and 1 <= i <= 24:
            pip += (i if p is Player.WHITE else (25 - i)) * pt.checkers
    return pip

def blot_count(board: Board, p: Player) -> int:
    return sum(1 for i, pt in enumerate(board.points) if 1 <= i <= 24 and pt.owner == p and pt.checkers == 1)

def anchor_count(board: Board, p: Player) -> int:
    return sum(1 for i, pt in enumerate(board.points) if 1 <= i <= 24 and pt.owner == p and pt.checkers >= 2)

def on_bar(board: Board, p: Player) -> int:
    return board.points[0 if p is Player.WHITE else 25].checkers

def borne_off(board: Board, p: Player) -> int:
    return board.points[25 if p is Player.WHITE else 0].checkers

def home_progress(board: Board, p: Player) -> float:
    home = set(range(1, 7)) if p is Player.WHITE else set(range(19, 25))
    off = 25 if p is Player.WHITE else 0
    total = inside = 0
    for i, pt in enumerate(board.points):
        if pt.owner == p:
            total += pt.checkers
            if i in home or i == off:
                inside += pt.checkers
    return (inside / total) if total else 1.0

def hits_made(prev: Board, nxt: Board, me: Player) -> int:
    return max(0, on_bar(nxt, opponent(me)) - on_bar(prev, opponent(me)))

def tri(x: float, a: float, b: float, c: float) -> float:
    if x <= a or x >= c: return 0.0
    if x == b: return 1.0
    if x < b: return (x - a) / (b - a + 1e-9)
    return (c - x) / (c - b + 1e-9)

def trap(x: float, a: float, b: float, c: float, d: float) -> float:
    if x <= a or x >= d: return 0.0
    if b <= x <= c: return 1.0
    if a < x < b: return (x - a) / (b - a + 1e-9)
    return (d - x) / (d - c + 1e-9)

@dataclass
class RouteFeatures:
    pip_gain: float
    hits: int
    blots_after: int
    anchors_after: int
    my_bar_after: int
    opp_bar_after: int
    home_progress_after: float
    borne_off_after: int

def extract_route_features(engine: Engine, route: TurnRoute) -> RouteFeatures:
    me = engine.turn
    before = engine.board
    pip_before = pip_count(before, me)

    e2 = copy.deepcopy(engine)
    e2.apply_route(route)
    after = e2.board

    return RouteFeatures(
        pip_gain = float(pip_before - pip_count(after, me)),
        hits = hits_made(before, after, me),
        blots_after = blot_count(after, me),
        anchors_after = anchor_count(after, me),
        my_bar_after = on_bar(after, me),
        opp_bar_after = on_bar(after, opponent(me)),
        home_progress_after = home_progress(after, me),
        borne_off_after = borne_off(after, me),
    )

@dataclass
class FuzzyWeights:
    out_centers: Tuple[float, float, float] = (0.2, 0.5, 0.85)

DEFAULT_OUT = FuzzyWeights()

def fuzzy_score(feat: RouteFeatures, out_centers: FuzzyWeights = DEFAULT_OUT) -> float:
    # membership
    pip_s = tri(feat.pip_gain, -2, 0, 4)
    pip_m = tri(feat.pip_gain, 2, 6, 10)
    pip_l = tri(feat.pip_gain, 8, 14, 22)
    hit_z = trap(feat.hits, -0.5, 0, 0, 0.5)
    hit_1 = tri(feat.hits, 0.5, 1, 1.5)
    hit_mn = tri(feat.hits, 1.5, 2, 3.5)
    bl_l = tri(feat.blots_after, -0.5, 0, 2)
    bl_m = tri(feat.blots_after, 1, 3, 5)
    bl_h = tri(feat.blots_after, 4, 7, 12)
    an_l = tri(feat.anchors_after, -0.5, 0, 1.5)
    an_m = tri(feat.anchors_after, 1, 2, 3.5)
    an_h = tri(feat.anchors_after, 3, 4, 6)
    myb_z = trap(feat.my_bar_after, -0.5, 0, 0, 0.5)
    myb_s = tri(feat.my_bar_after, 0.5, 1, 2.5)
    myb_mn = tri(feat.my_bar_after, 2, 3, 6)
    opb_z = trap(feat.opp_bar_after, -0.5, 0, 0, 0.5)
    opb_s = tri(feat.opp_bar_after, 0.5, 1, 2.5)
    opb_mn = tri(feat.opp_bar_after, 2, 3, 6)
    hm_l = tri(feat.home_progress_after, 0.10, 0.20, 0.35)
    hm_m = tri(feat.home_progress_after, 0.30, 0.50, 0.70)
    hm_h = tri(feat.home_progress_after, 0.65, 0.85, 1.01)
    off_l = tri(feat.borne_off_after, -0.5, 0, 3)
    off_m = tri(feat.borne_off_after, 2, 5, 9)
    off_h = tri(feat.borne_off_after, 8, 11, 15.5)

    # rules
    g = 0.0
    g = max(g, min(pip_l, bl_l, an_h))
    g = max(g, min(hit_1, bl_l, pip_m))
    g = max(g, min(hit_mn, bl_l))
    g = max(g, min(hm_h, bl_l))
    g = max(g, min(off_h, bl_l))
    g = max(g, min(opb_mn, bl_l))

    o = 0.0
    o = max(o, min(pip_m, bl_m))
    o = max(o, min(hit_1, bl_m))
    o = max(o, min(an_m, pip_s))
    o = max(o, min(hm_m, bl_m))
    o = max(o, min(off_m, bl_m))

    p = 0.0
    p = max(p, min(bl_h, pip_s))
    p = max(p, min(myb_s, pip_s))
    p = max(p, min(myb_mn, 1.0))
    p = max(p, min(hit_z, bl_h))

    cP, cO, cG = out_centers.out_centers
    num = p * cP + o * cO + g * cG
    den = (p + o + g) + 1e-9
    return num / den

@dataclass
class FuzzyDebug:
    scored: List[Tuple[TurnRoute, float, RouteFeatures]]

def pick_best_route_fuzzy(engine: Engine):
    routes = engine.generate_routes()
    if not routes:
        return None, 0.0, FuzzyDebug(scored=[])
    best_r = None; best_s = -1.0
    scored = []
    for r in routes:
        f = extract_route_features(engine, r)
        s = fuzzy_score(f)
        scored.append((r, s, f))
        if s > best_s:
            best_s, best_r = s, r
    return best_r, best_s, FuzzyDebug(scored=scored)
