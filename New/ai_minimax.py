# ai_minimax.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, List, Tuple, Optional
import math
import copy
import random

from engine_core import Engine, Board, Player, Move, TurnRoute, opponent

@dataclass
class EvalWeights:
    pip_weight: float = -0.9
    blot_weight: float = -0.8
    anchor_weight: float = +0.6
    bar_penalty: float = -1.2
    opp_bar_pressure: float = +0.7
    home_progress: float = +0.6
    borne_off_weight: float = +1.1
    blockade_weight: float = +0.4

DEFAULT_WEIGHTS = EvalWeights()

class Evaluator:
    @staticmethod
    def pip_count(board: Board, me: Player) -> int:
        pip = 0
        for i, pt in enumerate(board.points):
            if pt.owner == me and 1 <= i <= 24:
                if me is Player.WHITE:
                    pip += i * pt.checkers
                else:
                    pip += (25 - i) * pt.checkers
        return pip

    @staticmethod
    def blot_count(board: Board, me: Player) -> int:
        return sum(1 for i, pt in enumerate(board.points) if pt.owner == me and pt.checkers == 1 and 1 <= i <= 24)

    @staticmethod
    def anchor_count(board: Board, me: Player) -> int:
        return sum(1 for i, pt in enumerate(board.points) if pt.owner == me and pt.checkers >= 2 and 1 <= i <= 24)

    @staticmethod
    def count_on_bar(board: Board, p: Player) -> int:
        return board.points[0 if p is Player.WHITE else 25].checkers

    @staticmethod
    def count_borne_off(board: Board, p: Player) -> int:
        return board.points[25 if p is Player.WHITE else 0].checkers

    @staticmethod
    def home_progress(board: Board, me: Player) -> float:
        home = set(range(1, 7)) if me is Player.WHITE else set(range(19, 25))
        off_idx = 25 if me is Player.WHITE else 0
        total = 0
        inside = 0
        for i, pt in enumerate(board.points):
            if pt.owner == me:
                total += pt.checkers
                if i in home or i == off_idx:
                    inside += pt.checkers
        return (inside / total) if total else 1.0

    @staticmethod
    def blockade_score(board: Board, me: Player) -> float:
        opp = opponent(me)
        score = 0.0; run = 0
        for i in range(1, 25):
            pt = board.points[i]
            if pt.owner == me and pt.checkers >= 2:
                run += 1; score += 0.5 * run
            else:
                run = 0
        return score

    @staticmethod
    def evaluate(board: Board, side_to_move: Player, w: EvalWeights = DEFAULT_WEIGHTS) -> float:
        me = side_to_move; opp = opponent(me)
        pip_me = Evaluator.pip_count(board, me);   pip_opp = Evaluator.pip_count(board, opp)
        bl_me = Evaluator.blot_count(board, me);   bl_opp = Evaluator.blot_count(board, opp)
        an_me = Evaluator.anchor_count(board, me); an_opp = Evaluator.anchor_count(board, opp)
        bar_me = Evaluator.count_on_bar(board, me); bar_opp = Evaluator.count_on_bar(board, opp)
        off_me = Evaluator.count_borne_off(board, me); off_opp = Evaluator.count_borne_off(board, opp)
        hm_me = Evaluator.home_progress(board, me); hm_opp = Evaluator.home_progress(board, opp)
        blk_me = Evaluator.blockade_score(board, me); blk_opp = Evaluator.blockade_score(board, opp)

        score = 0.0
        score += w.pip_weight * pip_me + (-w.pip_weight) * pip_opp
        score += w.blot_weight * bl_me + (-w.blot_weight) * bl_opp
        score += w.anchor_weight * (an_me - an_opp)
        score += w.bar_penalty * bar_me + w.opp_bar_pressure * bar_opp
        score += w.home_progress * (hm_me - hm_opp)
        score += w.borne_off_weight * (off_me - off_opp)
        score += w.blockade_weight * (blk_me - blk_opp)
        return score

@dataclass
class SearchDebug:
    nodes: int = 0
    leaf_evals: int = 0
    best_line: List[TurnRoute] = None

def _apply_route_on_clone(engine: Engine, route: TurnRoute) -> Engine:
    e2 = copy.deepcopy(engine)
    e2.apply_route(route)
    e2.end_turn()
    return e2

def _opponent_roll(engine: Engine) -> Engine:
    e2 = copy.deepcopy(engine); e2.roll(); return e2

def _terminal_eval(engine: Engine, eval_fn) -> float:
    return eval_fn(engine.board, engine.turn)

def minimax(engine: Engine, depth: int, eval_fn, alpha=-math.inf, beta=math.inf, debug: Optional[SearchDebug] = None):
    if debug is None:
        debug = SearchDebug(nodes=0, leaf_evals=0, best_line=[])
    debug.nodes += 1

    routes = engine.generate_routes()
    if depth == 0 or not routes:
        debug.leaf_evals += 1
        return _terminal_eval(engine, eval_fn), []

    best_score = -math.inf
    best_line: List[TurnRoute] = []

    for r in routes:
        after_my = _apply_route_on_clone(engine, r)
        after_opp_roll = _opponent_roll(after_my)
        opp_routes = after_opp_roll.generate_routes()

        if not opp_routes or depth - 1 == 0:
            score = _terminal_eval(after_opp_roll, eval_fn)
            line = [r]
        else:
            worst_for_me = +math.inf
            worst_reply_line: List[TurnRoute] = []
            for oroute in opp_routes:
                after_opp = _apply_route_on_clone(after_opp_roll, oroute)
                if depth - 2 > 0:
                    after_opp.roll()
                sc, subline = minimax(after_opp, depth - 2, eval_fn, -beta, -alpha, debug)
                sc = -sc
                if sc < worst_for_me:
                    worst_for_me = sc
                    worst_reply_line = [r, oroute] + subline
                beta = min(beta, -worst_for_me)
                if alpha >= beta:
                    break
            score = worst_for_me
            line = worst_reply_line

        if score > best_score or (math.isclose(score, best_score) and random.random() < 0.5):
            best_score = score
            best_line = line

        alpha = max(alpha, best_score)
        if alpha >= beta:
            break

    return best_score, best_line

def pick_best_route(engine: Engine, depth: int = 2, eval_weights: EvalWeights = DEFAULT_WEIGHTS):
    def eval_fn(board: Board, side: Player) -> float:
        return Evaluator.evaluate(board, side, eval_weights)

    debug = SearchDebug(nodes=0, leaf_evals=0, best_line=[])
    score, line = minimax(engine, depth, eval_fn, debug=debug)
    best_route = line[0] if line else None
    debug.best_line = line
    return best_route, score, debug
