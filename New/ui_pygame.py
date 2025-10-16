# ui_pygame.py
import sys, traceback, pygame
from typing import Dict, List, Tuple, Optional
from engine_core import Engine, Player, TurnRoute, Move
from ai_minimax import pick_best_route
from ai_fuzzy import pick_best_route_fuzzy

pygame.init()
pygame.display.set_caption("Backgammon — Pygame UI")

W, H = 1100, 720
PAD = 20
BOARD_W, BOARD_H = W - 2 * PAD, H - 130
POINT_W = BOARD_W // 14
POINT_H = BOARD_H // 2
BAR_W = POINT_W
FPS = 60

BG_COL = (28, 33, 41)
WOOD_DARK = (74, 55, 35)
WOOD_LIGHT = (182, 152, 113)
TRI_A = (214, 95, 64)
TRI_B = (242, 209, 149)
CHECK_WHITE = (236, 236, 236)
CHECK_BLACK = (28, 28, 28)
ACCENT = (130, 200, 250)
HILITE = (90, 200, 120)
TEXT = (235, 235, 235)
DICE_BG = (45, 52, 60)

FONT = pygame.font.SysFont("arial", 18)
FONT_BIG = pygame.font.SysFont("arial", 24, bold=True)
FONT_HUGE = pygame.font.SysFont("arial", 36, bold=True)

def layout_rects() -> Dict[str, pygame.Rect]:
    board_rect = pygame.Rect(PAD, 90, BOARD_W, BOARD_H)
    dice_rect = pygame.Rect(PAD, 20, 420, 56)
    info_rect = pygame.Rect(PAD + 430, 20, W - PAD - 430 - PAD, 56)
    return {"board": board_rect, "dice": dice_rect, "info": info_rect}

LAYOUT = layout_rects()

# ───────────────────── geometry helpers ─────────────────────

def point_screen_pos(point_idx: int) -> Tuple[int, int]:
    board = LAYOUT["board"]

    def col_for_order(n_from_left: int) -> int:
        # columns: 0..5 (left block), skip bar col, 6..11 (right block)
        return n_from_left if n_from_left < 6 else n_from_left + 1

    # top row 24..13
    if 13 <= point_idx <= 24:
        n = 24 - point_idx
        col = col_for_order(n)
        return (board.left + col * POINT_W + POINT_W // 2, board.top)

    # bottom row 1..12
    if 1 <= point_idx <= 12:
        n = point_idx - 1
        col = col_for_order(n)
        return (board.left + col * POINT_W + POINT_W // 2, board.bottom)

    # special pockets (separate bars/offs; engine uses 0/25 for WHITE, 26/27 for BLACK)
    if point_idx == 0:      # WHITE BAR
        return (board.left + 6 * POINT_W + POINT_W // 2, board.centery - 30)
    if point_idx == 26:     # BLACK BAR
        return (board.left + 6 * POINT_W + POINT_W // 2, board.centery + 30)
    if point_idx == 25:     # WHITE OFF
        return (board.right - POINT_W // 2, board.centery - 20)
    if point_idx == 27:     # BLACK OFF
        return (board.right - POINT_W // 2, board.centery + 20)

    return (W // 2, H // 2)

def point_polygon(point_idx: int) -> List[Tuple[int, int]]:
    cx, base = point_screen_pos(point_idx)
    half = max(2, POINT_W // 2 - 6)
    height = max(8, POINT_H - 16)
    if 13 <= point_idx <= 24:
        return [(cx - half, base), (cx + half, base), (cx, base + height)]
    if 1 <= point_idx <= 12:
        return [(cx - half, base), (cx + half, base), (cx, base - height)]
    return []

def point_at_pos(mx: int, my: int) -> Optional[int]:
    # center bar column
    bar_rect = pygame.Rect(LAYOUT["board"].left + 6 * POINT_W, LAYOUT["board"].top, BAR_W, BOARD_H)
    if bar_rect.collidepoint(mx, my):
        return None  # UI maps to the mover's bar if needed
    for idx in list(range(24, 13 - 1, -1)) + list(range(1, 13)):
        poly = point_polygon(idx)
        if not poly:
            continue
        if point_in_triangle((mx, my), poly[0], poly[1], poly[2]):
            return idx
    return None

def point_in_triangle(p, a, b, c):
    (px, py), (x1, y1), (x2, y2), (x3, y3) = p, a, b, c
    denom = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if abs(denom) < 1e-9:
        return False
    w1 = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / denom
    w2 = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / denom
    w3 = 1 - w1 - w2
    return (w1 >= 0) and (w2 >= 0) and (w3 >= 0)

# ───────────────────── drawing ─────────────────────

def draw_board(surface: pygame.Surface):
    surface.fill(BG_COL)
    board = LAYOUT["board"]
    pygame.draw.rect(surface, WOOD_DARK, board, border_radius=14)

    # top 12 (24..13)
    for n in range(12):
        idx = 24 - n
        color = TRI_A if (n % 2 == 0) else TRI_B
        pygame.draw.polygon(surface, color, point_polygon(idx))

    # bottom 12 (1..12)
    for n in range(12):
        idx = n + 1
        color = TRI_A if (n % 2 == 0) else TRI_B
        pygame.draw.polygon(surface, color, point_polygon(idx))

    # center bar and off gutter
    bar_rect = pygame.Rect(board.left + 6 * POINT_W, board.top, BAR_W, BOARD_H)
    pygame.draw.rect(surface, WOOD_LIGHT, bar_rect)
    off_rect = pygame.Rect(board.right - POINT_W, board.top, POINT_W, BOARD_H)
    pygame.draw.rect(surface, WOOD_LIGHT, off_rect, border_radius=8)

    pygame.draw.rect(surface, DICE_BG, LAYOUT["dice"], border_radius=10)
    pygame.draw.rect(surface, DICE_BG, LAYOUT["info"], border_radius=10)

def draw_checkers(surface: pygame.Surface, eng: Engine):
    for idx in range(28):
        pt = eng.board.points[idx]
        if pt.owner is None or pt.checkers == 0:
            continue

        cx, base = point_screen_pos(idx)
        color = CHECK_WHITE if pt.owner is Player.WHITE else CHECK_BLACK
        outline = (30, 30, 30) if pt.owner is Player.WHITE else (220, 220, 220)

        radius = max(8, min(POINT_W, POINT_H) // 2 - 6)
        gap = radius + 6

        # stacking policy
        if 1 <= idx <= 12:
            y0 = LAYOUT["board"].bottom - radius - 6; step = -gap
        elif 13 <= idx <= 24:
            y0 = LAYOUT["board"].top + radius + 6; step = +gap
        elif idx in (25, 27):  # OFF pockets: stack upward
            y0 = base; step = -gap
        elif idx in (0, 26):   # BAR pockets: stack away from center
            y0 = base; step = +gap if pt.owner is Player.WHITE else -gap
        else:
            y0 = base; step = -gap

        count = pt.checkers
        max_draw = 6
        for k in range(min(count, max_draw)):
            y = y0 + step * k
            pygame.draw.circle(surface, color, (cx, int(y)), radius)
            pygame.draw.circle(surface, outline, (cx, int(y)), radius, 2)
        if count > max_draw:
            tag = FONT.render(f"+{count - max_draw}", True, TEXT)
            surface.blit(tag, (cx - tag.get_width() // 2, y0 + step * (max_draw - 1) - 12))

def draw_dice(surface: pygame.Surface, eng: Engine, ai_label: str):
    rect = LAYOUT["dice"]
    txt_turn = "WHITE (You) to move" if eng.turn is Player.WHITE else f"BLACK (AI: {ai_label}) to move"
    surface.blit(FONT_BIG.render(txt_turn, True, TEXT), (rect.x + 12, rect.y + 6))
    surface.blit(FONT.render("DICE:", True, TEXT), (rect.x + 12, rect.y + 32))
    x = rect.x + 60
    for d in eng.dice:
        die_rect = pygame.Rect(x, rect.y + 26, 34, 24)
        pygame.draw.rect(surface, (240, 240, 240), die_rect, border_radius=4)
        pygame.draw.rect(surface, (40, 40, 40), die_rect, 2, border_radius=4)
        surface.blit(FONT.render(str(d), True, (20, 20, 20)), (die_rect.x + 12, die_rect.y + 3))
        x += 40

def draw_info(surface: pygame.Surface, hint: str):
    rect = LAYOUT["info"]
    help1 = "[R] Roll   [F] Finish turn   [N] New game"
    surface.blit(FONT.render(help1, True, TEXT), (rect.x + 12, rect.y + 8))
    msg = hint if len(hint) < 90 else hint[:87] + "..."
    surface.blit(FONT.render(msg, True, TEXT), (rect.x + 12, rect.y + 32))

def draw_highlights(surface: pygame.Surface, starts: List[int], targets: List[int]):
    for s in starts:
        poly = point_polygon(s)
        if poly:
            pygame.draw.polygon(surface, ACCENT, poly, 4)
    for t in targets:
        poly = point_polygon(t)
        if poly:
            pygame.draw.polygon(surface, HILITE, poly, 6)

def draw_game_over(surface: pygame.Surface, winner: Player):
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 140))
    surface.blit(overlay, (0, 0))
    msg = "WHITE wins!" if winner is Player.WHITE else "BLACK wins!"
    sub = "Press [N] for a new game."
    title = FONT_HUGE.render(msg, True, (255, 255, 255))
    line2 = FONT.render(sub, True, (230, 230, 230))
    surface.blit(title, (W // 2 - title.get_width() // 2, H // 2 - 28))
    surface.blit(line2, (W // 2 - line2.get_width() // 2, H // 2 + 10))

# ───────────────────── UI state ─────────────────────

class UIState:
    def __init__(self, eng: Engine, ai_mode: str):
        self.eng = eng
        self.selected_start: Optional[int] = None
        self.legal_map: Dict[int, List[int]] = {}
        self.target_die: Dict[Tuple[int, int], int] = {}
        self.hint = "Press [R] to roll at start of your turn."
        self.ai_mode = ai_mode  # "Minimax" or "Fuzzy"
        self.ai_label = "Edith" if ai_mode == "Minimax" else "Jarvis"
        self.ai_sides = {Player.WHITE: False, Player.BLACK: True}  # White=Human, Black=AI
        self.ai_auto = True
        self._ai_busy = False

        # game over flags
        self.game_over = False
        self.winner: Optional[Player] = None

    # ---------- game-over checks ----------
    def _check_game_over(self):
        if self.eng.has_won(Player.WHITE):
            self.game_over = True
            self.winner = Player.WHITE
            self.hint = "WHITE wins! Press [N] for a new game."
        elif self.eng.has_won(Player.BLACK):
            self.game_over = True
            self.winner = Player.BLACK
            self.hint = "BLACK wins! Press [N] for a new game."

    # ---------- legals / selection ----------
    def refresh_legals(self):
        self.legal_map.clear(); self.target_die.clear()
        starts = list(range(1, 25))
        bar_idx = self.eng.board.bar_index(self.eng.turn)
        if self.eng.board.points[bar_idx].checkers > 0:
            starts = [bar_idx]  # must enter from bar
        for s in starts:
            pairs = self.eng.legal_targets_from(s)
            if not pairs:
                continue
            ends = []
            for die, end in pairs:
                ends.append(end)
                key = (s, end)
                if key in self.target_die:
                    self.target_die[key] = min(self.target_die[key], die)
                else:
                    self.target_die[key] = die
            self.legal_map[s] = sorted(set(ends))

    def current_targets(self) -> List[int]:
        if self.selected_start is None:
            return []
        return self.legal_map.get(self.selected_start, [])

    def selectable_starts(self) -> List[int]:
        return sorted(self.legal_map.keys())

    def has_any_legal(self) -> bool:
        # Recompute to avoid stale state when user presses F
        self.refresh_legals()
        return len(self.legal_map) > 0

    # ---------- moves ----------
    def apply_single(self, start: int, end: int) -> bool:
        try:
            if self.game_over:
                return False
            if start not in self.legal_map or end not in self.legal_map[start]:
                return False
            die = self.target_die.get((start, end))
            if die is None:
                return False
            self.eng.apply_route(TurnRoute(moves=[Move(start=start, end=end, die=die)]))
            self.refresh_legals()
            self._check_game_over()
            if self.game_over:
                return True
            if (not self.eng.dice) or (len(self.legal_map) == 0):
                self.end_turn()
            return True
        except Exception as e:
            self.hint = f"apply error: {e}"
            traceback.print_exc()
            return False

    def end_turn(self):
        if self.game_over:
            return
        self.eng.end_turn()
        self.selected_start = None
        self.legal_map.clear()
        self.target_die.clear()
        self.hint = "Press [R] to roll."

    def try_roll(self):
        if self.game_over:
            self.hint = "Game over. Press [N] for a new game."
            return
        if self.eng.dice:
            self.hint = "Dice already rolled. Use them or [F] to finish if stuck."
            return
        self.eng.roll()
        self.refresh_legals()
        if len(self.legal_map) == 0:
            self.hint = "No legal moves — passing the turn."
            self.end_turn()
        else:
            self.hint = "Click a point to move. Targets will highlight."

    # ---------- AI ----------
    def pick_route(self) -> Optional[TurnRoute]:
        if self.ai_mode == "Minimax":
            r, _, _ = pick_best_route(self.eng, depth=2)
        else:
            r, _, _ = pick_best_route_fuzzy(self.eng)
        return r

    def run_ai_if_needed(self):
        if self.game_over:
            return
        if not self.ai_auto or not self.ai_sides.get(self.eng.turn, False) or self._ai_busy:
            return
        self._ai_busy = True
        try:
            if not self.eng.dice:
                self.try_roll()
                if self.game_over or not self.ai_sides.get(self.eng.turn, False):
                    return
                if not self.eng.dice:
                    return
            route = self.pick_route()
            if route and route.moves:
                for m in route.moves:
                    self.eng.apply_route(TurnRoute(moves=[m]))
                self.hint = f"BLACK ({self.ai_label}) moved."
            else:
                self.hint = f"BLACK ({self.ai_label}) has no legal move — passing."
            self._check_game_over()
            if not self.game_over:
                self.end_turn()
        except Exception as e:
            self.hint = f"AI error: {e}"
            traceback.print_exc()
        finally:
            self._ai_busy = False

# ───────────────────── start screen ─────────────────────

def start_screen(screen) -> str:
    """Return 'Minimax' or 'Fuzzy' based on 1/2 key."""
    clock = pygame.time.Clock()
    choice = None
    while choice is None:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_1:
                    choice = "Minimax"
                elif e.key == pygame.K_2:
                    choice = "Fuzzy"

        screen.fill(BG_COL)
        title = FONT_HUGE.render("Choose your opponent", True, TEXT)
        o1 = FONT_BIG.render("1) Edith  — Minimax", True, TEXT)
        o2 = FONT_BIG.render("2) Jarvis — Fuzzy", True, TEXT)
        tip = FONT.render("White is YOU. Black is the AI and will auto-move.", True, TEXT)
        screen.blit(title, (W // 2 - title.get_width() // 2, 180))
        screen.blit(o1, (W // 2 - o1.get_width() // 2, 260))
        screen.blit(o2, (W // 2 - o2.get_width() // 2, 300))
        screen.blit(tip, (W // 2 - tip.get_width() // 2, 360))
        pygame.display.flip()
        clock.tick(60)
    return choice

# ───────────────────── main loop ─────────────────────

def main():
    screen = pygame.display.set_mode((W, H))
    ai_mode = start_screen(screen)  # "Minimax" or "Fuzzy"

    clock = pygame.time.Clock()
    eng = Engine()
    ui = UIState(eng, ai_mode)

    running = True
    while running:
        try:
            dt = clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_n:
                        eng.new_game()
                        ui = UIState(eng, ai_mode)
                    elif event.key == pygame.K_r:
                        ui.try_roll()
                    elif event.key == pygame.K_f:
                        if not eng.dice:
                            ui.end_turn()
                        else:
                            # refresh and pass if truly stuck
                            if not ui.has_any_legal():
                                ui.hint = "No legal moves — passing the turn."
                                ui.end_turn()
                            else:
                                ui.hint = "You still have playable dice."

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    clicked_idx = None
                    # clicking bar column maps to current player's bar if checkers present
                    bar_rect = pygame.Rect(LAYOUT["board"].left + 6 * POINT_W, LAYOUT["board"].top, BAR_W, BOARD_H)
                    if bar_rect.collidepoint(mx, my):
                        bar_idx = eng.board.bar_index(eng.turn)
                        if eng.board.points[bar_idx].checkers > 0:
                            clicked_idx = bar_idx
                    if clicked_idx is None:
                        clicked_idx = point_at_pos(mx, my)

                    if clicked_idx is not None:
                        if not eng.dice:
                            ui.hint = "Press [R] to roll first."
                        else:
                            if ui.selected_start is None:
                                ui.refresh_legals()
                                if clicked_idx in ui.legal_map:
                                    ui.selected_start = clicked_idx
                                    ui.hint = "Select a highlighted target."
                                else:
                                    ui.hint = "No legal moves from there."
                            else:
                                if clicked_idx == ui.selected_start:
                                    ui.selected_start = None
                                elif clicked_idx in ui.current_targets():
                                    ok = ui.apply_single(ui.selected_start, clicked_idx)
                                    ui.selected_start = None
                                    ui.hint = "Move applied." if ok else "Could not move."
                                else:
                                    ui.refresh_legals()
                                    if clicked_idx in ui.legal_map:
                                        ui.selected_start = clicked_idx
                                    else:
                                        ui.selected_start = None

            # Auto AI for Black when it's their turn
            ui.run_ai_if_needed()

            # Auto-pass if dice exist but no legal moves remain (and not game over)
            if not ui.game_over and eng.dice and not ui.has_any_legal() and not ui.ai_sides.get(eng.turn, False):
                ui.hint = "No legal moves — passing the turn."
                ui.end_turn()

            # Draw
            draw_board(screen)
            draw_checkers(screen, eng)
            draw_dice(screen, eng, ui.ai_label)
            starts = ui.selectable_starts()
            targs = ui.current_targets()
            draw_highlights(screen, starts if ui.selected_start is None else [ui.selected_start], targs)
            draw_info(screen, ui.hint)
            if ui.game_over and ui.winner is not None:
                draw_game_over(screen, ui.winner)
            pygame.display.flip()

        except Exception as e:
            ui.hint = f"Runtime error: {e}"
            traceback.print_exc()

    pygame.quit()

if __name__ == "__main__":
    main()
