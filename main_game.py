# main_game.py
# Smart Gammon - simplified, complete board + playable UI (Tkinter)
# - Human plays White, AI plays Black (random placeholder)
# - Basic rules: roll two dice, move checkers forward towards bearing-off
# - Hitting + bar + re-entry + bearing off implemented
# - Hooks: run_fuzzy_ai(), run_minimax_ai() to implement advanced AI

import tkinter as tk
from tkinter import messagebox, font
import random
import copy

# -----------------------
# Configuration / layout
# -----------------------
WINDOW_W = 1000
WINDOW_H = 520
BOARD_W = 760
BOARD_H = 480
MARGIN = 10
POINT_W = (BOARD_W - 2 * MARGIN) / 24.0

WHITE = "#FFFFFF"
BLACK = "#000000"
WOOD1 = "#A67C52"
WOOD2 = "#8A6239"
GREEN = "#0F3D2E"
HIGHLIGHT = "#FFD966"
CHECKER_SHADOW = "#333333"

# Home quadrants (assuming both run left->right for simpler coherence)
# We'll use standard starting but unified direction: both players move from point 1 -> 24
# Home for human (white) is points 19..24, for AI (black) 1..6
WHITE_HOME = list(range(19, 25))
BLACK_HOME = list(range(1, 7))

# -----------------------
# Game state structures
# -----------------------
class Point:
    def __init__(self, idx):
        self.idx = idx  # 1..24
        self.white = 0
        self.black = 0

    def total(self):
        return self.white + self.black

    def owner(self):
        if self.white > 0 and self.black == 0:
            return 'white'
        if self.black > 0 and self.white == 0:
            return 'black'
        return None

class GameState:
    def __init__(self):
        # points 1..24
        self.points = {i: Point(i) for i in range(1, 25)}
        # bar counts
        self.bar_white = 0
        self.bar_black = 0
        # borne off
        self.off_white = 0
        self.off_black = 0
        # dice
        self.dice = []
        # whose turn: 'white' (player) or 'black' (ai)
        self.turn = 'white'
        # moves remaining expressed as list of dice values still usable
        self.moves_remaining = []
        # selection
        self.selected_point = None
        # game over flag
        self.game_over = False
        self.setup_initial()

    def setup_initial(self):
        # Standard setup (classic distribution) but adapted for our 1..24 orientation:
        # We'll follow one common orientation:
        # White: 2 on 1, 5 on 12, 3 on 17, 5 on 19 (this is close to the report used)
        # Black: symmetric on the opposite side
        for p in self.points.values():
            p.white = 0
            p.black = 0
        # White placement
        self.points[1].white = 2
        self.points[12].white = 5
        self.points[17].white = 3
        self.points[19].white = 5
        # Black placement (mirror-ish)
        self.points[24].black = 2
        self.points[13].black = 5
        self.points[8].black = 3
        self.points[6].black = 5

        self.bar_white = 0
        self.bar_black = 0
        self.off_white = 0
        self.off_black = 0
        self.dice = []
        self.turn = 'white'
        self.moves_remaining = []
        self.selected_point = None
        self.game_over = False

    def clone(self):
        return copy.deepcopy(self)


# -----------------------
# Utility functions
# -----------------------
def roll_two_dice():
    a = random.randint(1, 6)
    b = random.randint(1, 6)
    if a == b:  # doubles: four moves of same value
        return [a, a, a, a]
    else:
        return [a, b]

def all_in_home(state: GameState, color):
    # checks if all checkers of color are in their home quadrant or borne off
    if color == 'white':
        home_pts = WHITE_HOME
        total_on_board = sum(p.white for p in state.points.values())
        # if there are checkers on bar -> not all in home
        if state.bar_white > 0:
            return False
        for idx, p in state.points.items():
            if p.white > 0 and idx not in home_pts:
                return False
        # if none on board outside home, return True
        return True
    else:
        home_pts = BLACK_HOME
        if state.bar_black > 0:
            return False
        for idx, p in state.points.items():
            if p.black > 0 and idx not in home_pts:
                return False
        return True

def bearing_off_allowed(state: GameState, color):
    return all_in_home(state, color)

def point_has_blocking_color(point: Point, moving_color):
    # move blocked if opponent has 2 or more on that point
    if moving_color == 'white':
        return point.black >= 2
    else:
        return point.white >= 2

def send_to_bar(state: GameState, color):
    if color == 'white':
        state.bar_white += 1
    else:
        state.bar_black += 1

def remove_from_bar(state: GameState, color):
    if color == 'white':
        if state.bar_white > 0:
            state.bar_white -= 1
            return True
        return False
    else:
        if state.bar_black > 0:
            state.bar_black -= 1
            return True
        return False

def add_off(state: GameState, color):
    if color == 'white':
        state.off_white += 1
    else:
        state.off_black += 1

def opponent(color):
    return 'black' if color == 'white' else 'white'

# -----------------------
# Legal moves computation
# -----------------------
def legal_moves_from_point(state: GameState, from_idx, color):
    """
    Given a state, a starting point index and color, compute legal target indices
    according to remaining moves in state.moves_remaining.
    Handles bar re-entry and bearing-off if allowed.
    Returns list of tuples (dice_used, target_idx, is_bearing_off_bool)
    target_idx uses 1..24; for bearing off target_idx = 0 for white beyond 24, and 25 for black beyond 24.
    """
    moves = []
    if color == 'white':
        direction = 1  # we define movement as increasing idx 1->24
    else:
        direction = 1  # AI uses same direction in this simplified version

    # If player has checkers on bar, they must re-enter first.
    if (color == 'white' and state.bar_white > 0) or (color == 'black' and state.bar_black > 0):
        # re-entry positions for bar: use dice to move onto point == dice value (white or black same in this simpler scheme)
        for die in set(state.moves_remaining):
            target = die  # simple re-entry at point == dice value
            if 1 <= target <= 24:
                point = state.points[target]
                if not point_has_blocking_color(point, color):
                    moves.append((die, target, False))
        return moves

    # If moving from a normal point:
    if from_idx < 1 or from_idx > 24:
        return moves

    for die in set(state.moves_remaining):
        target = from_idx + die * direction
        # Bearing off check:
        if target > 24:
            # allowed only if all in home
            if bearing_off_allowed(state, color):
                moves.append((die, 0 if color == 'white' else 25, True))
            # else not allowed
        else:
            # check if blocked
            pt = state.points[target]
            if not point_has_blocking_color(pt, color):
                moves.append((die, target, False))
    return moves

def all_legal_moves(state: GameState, color):
    """Return list of moves in the form (from_idx, die, target_idx, is_bearoff)"""
    moves = []
    # if color has bar checkers must re-enter
    has_bar = (state.bar_white > 0 if color == 'white' else state.bar_black > 0)
    if has_bar:
        # create pseudo-from index 'bar' as 0
        for die in set(state.moves_remaining):
            target = die
            if 1 <= target <= 24:
                pt = state.points[target]
                if not point_has_blocking_color(pt, color):
                    moves.append(('bar', die, target, False))
        return moves

    # iterate over points that have player's checkers
    for idx in range(1, 25):
        p = state.points[idx]
        if (color == 'white' and p.white > 0) or (color == 'black' and p.black > 0):
            for (die, tgt, is_bear) in legal_moves_from_point(state, idx, color):
                moves.append((idx, die, tgt, is_bear))
    return moves

# Apply a move to a GameState (mutates it)
def apply_move(state: GameState, from_idx, die, target_idx, color, is_bearoff=False):
    """
    from_idx: 1..24 or 'bar'
    target_idx: 1..24 or 0 (white off) or 25 (black off)
    """
    # consume one die instance
    if die in state.moves_remaining:
        state.moves_remaining.remove(die)
    else:
        # die may be missing due to order; try to remove any equivalent (for doubles)
        if state.moves_remaining:
            state.moves_remaining.pop(0)

    # removing piece from source
    if from_idx == 'bar':
        remove_from_bar(state, color)
    else:
        if color == 'white':
            state.points[from_idx].white -= 1
        else:
            state.points[from_idx].black -= 1

    # applying to target
    if is_bearoff:
        add_off(state, color)
    else:
        # if target occupied by single enemy, hit it
        if target_idx == 0 or target_idx == 25:
            # shouldn't happen here
            add_off(state, color)
            return
        tgt_pt = state.points[target_idx]
        if color == 'white':
            # if single enemy checker -> hit
            if tgt_pt.black == 1 and tgt_pt.white == 0:
                tgt_pt.black -= 1
                send_to_bar(state, 'black')
            tgt_pt.white += 1
        else:
            if tgt_pt.white == 1 and tgt_pt.black == 0:
                tgt_pt.white -= 1
                send_to_bar(state, 'white')
            tgt_pt.black += 1

# -----------------------
# Simple AI placeholders
# -----------------------
def run_random_ai_move(state: GameState):
    # Choose one random legal move and apply; iterate until moves exhausted
    while True:
        moves = all_legal_moves(state, 'black')
        if not moves or not state.moves_remaining:
            break
        # prefer moves that hit opponent (greedy)
        hits = [m for m in moves if m[2] not in (0, 25) and ((state.points[m[2]].white == 1 and m[0] != 'bar'))]
        if hits:
            move = random.choice(hits)
        else:
            move = random.choice(moves)
        from_idx, die, target_idx, is_bear = move
        apply_move(state, from_idx, die, target_idx, 'black', is_bear)
    # switch to white
    state.turn = 'white'
    state.moves_remaining = []
    check_game_end(state)

def run_fuzzy_ai(state: GameState):
    # Hook: implement fuzzy decision making here
    # For now, call random
    run_random_ai_move(state)

def run_minimax_ai(state: GameState):
    # Hook: implement minimax + evaluation -> apply moves
    # For now, call random
    run_random_ai_move(state)

# -----------------------
# UI / Tkinter
# -----------------------
class SmartGammonUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Gammon")
        self.state = GameState()
        self.canvas = tk.Canvas(root, width=BOARD_W, height=BOARD_H, bg=WOOD1)
        self.canvas.pack(side=tk.LEFT, padx=10, pady=10)
        # Right panel
        self.panel = tk.Frame(root, width=WINDOW_W - BOARD_W - 40)
        self.panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        self.title_label = tk.Label(self.panel, text="Smart Gammon", font=("Consolas", 20, "bold"))
        self.title_label.pack(pady=(0, 10))

        self.info_text = tk.Label(self.panel, text="", justify=tk.LEFT, font=("Consolas", 11))
        self.info_text.pack(pady=(0, 10))

        btn_frame = tk.Frame(self.panel)
        btn_frame.pack(pady=8)
        self.roll_btn = tk.Button(btn_frame, text="Roll Dice", command=self.on_roll, width=12)
        self.roll_btn.grid(row=0, column=0, padx=5, pady=5)
        self.rand_ai_btn = tk.Button(btn_frame, text="AI: Random", command=self.set_ai_random)
        self.rand_ai_btn.grid(row=0, column=1, padx=5)
        self.fuzzy_ai_btn = tk.Button(btn_frame, text="AI: Fuzzy", command=self.set_ai_fuzzy)
        self.fuzzy_ai_btn.grid(row=1, column=0, padx=5, pady=5)
        self.minimax_ai_btn = tk.Button(btn_frame, text="AI: Minimax", command=self.set_ai_minimax)
        self.minimax_ai_btn.grid(row=1, column=1, padx=5, pady=5)
        self.reset_btn = tk.Button(self.panel, text="Restart Game", command=self.restart_game)
        self.reset_btn.pack(pady=12)

        # status
        self.ai_mode = 'random'  # 'random'|'fuzzy'|'minimax'
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.draw_everything()
        self.update_info()

    def set_ai_random(self):
        self.ai_mode = 'random'
        self.update_info()

    def set_ai_fuzzy(self):
        self.ai_mode = 'fuzzy'
        self.update_info()

    def set_ai_minimax(self):
        self.ai_mode = 'minimax'
        self.update_info()

    def restart_game(self):
        self.state.setup_initial()
        self.draw_everything()
        self.update_info()

    def on_roll(self):
        if self.state.game_over:
            messagebox.showinfo("Game over", "Game is finished. Restart to play again.")
            return

        # only allow roll on player's turn and when moves_remaining empty
        if self.state.turn != 'white' or self.state.moves_remaining:
            return

        self.state.dice = roll_two_dice()
        self.state.moves_remaining = self.state.dice.copy()
        self.update_info()
        self.draw_everything()

        # If player has no legal move immediately, pass turn
        moves = all_legal_moves(self.state, 'white')
        if not moves:
            self.end_player_turn()

    def end_player_turn(self):
        # Player finished moves or no moves -> AI's turn
        self.state.turn = 'black'
        # run AI move according to ai_mode
        if self.ai_mode == 'random':
            run_random_ai_move(self.state)
        elif self.ai_mode == 'fuzzy':
            run_fuzzy_ai(self.state)
        else:
            run_minimax_ai(self.state)
        # after AI move, update UI
        self.draw_everything()
        self.update_info()

    def on_canvas_click(self, event):
        # detect clicked point (1..24)
        x = event.x
        # map x to point index
        idx = int((x - MARGIN) / POINT_W) + 1
        if idx < 1 or idx > 24:
            return

        # if it's player's turn and they have moves
        if self.state.turn != 'white' or not self.state.moves_remaining:
            return

        # if player has bar checkers they must re-enter
        if self.state.bar_white > 0:
            # clicking a point attempts to re-enter using appropriate die; check legal
            # re-entry uses dice values as target indexes in our simplified scheme
            chosen_target = idx
            possible = [('bar', die, chosen_target, False) for die in set(self.state.moves_remaining)
                        if 1 <= chosen_target <= 24 and not point_has_blocking_color(self.state.points[chosen_target], 'white') and die == chosen_target]
            # fallback: if die value equals chosen_target
            if possible:
                _, die, t, is_bear = possible[0]
                apply_move(self.state, 'bar', die, t, 'white', is_bear)
            else:
                # show hint
                self.info_text['text'] = "You must re-enter from bar when you have checkers on bar."
            self.draw_everything()
            # if no moves left for player -> end turn
            if not self.state.moves_remaining:
                self.end_player_turn()
            return

        # normal flow: select source or attempt move
        if self.state.selected_point is None:
            # select only if there is a white checker
            if self.state.points[idx].white > 0:
                self.state.selected_point = idx
                self.draw_everything()
                self.update_info()
        else:
            # attempt to move selected_point -> idx using one of dice
            from_idx = self.state.selected_point
            legal = legal_moves_from_point(self.state, from_idx, 'white')
            chosen = None
            for die, tgt, is_bear in legal:
                if tgt == idx:
                    chosen = (die, tgt, is_bear)
                    break
            # bearing off with click beyond board: allow click on last column for off?
            if chosen:
                die, tgt, is_bear = chosen
                apply_move(self.state, from_idx, die, tgt, 'white', is_bear)
                self.state.selected_point = None
                self.draw_everything()
                self.update_info()
                # if no moves remaining -> end turn
                if not self.state.moves_remaining:
                    self.end_player_turn()
            else:
                # maybe clicked a different source to select instead
                if self.state.points[idx].white > 0:
                    self.state.selected_point = idx
                else:
                    # invalid target -> deselect
                    self.state.selected_point = None
                self.draw_everything()
                self.update_info()

    def draw_everything(self):
        self.canvas.delete("all")
        # draw board background
        self.canvas.create_rectangle(0, 0, BOARD_W, BOARD_H, fill=WOOD2, outline="")
        # draw mid line and bar
        self.canvas.create_rectangle(BOARD_W/2 - 20, 0, BOARD_W/2 + 20, BOARD_H, fill=WOOD1, outline="")

        # draw points (triangles)
        for i in range(1, 25):
            x0 = MARGIN + (i - 1) * POINT_W
            x1 = x0 + POINT_W
            # alternate colors
            is_up = (i % 2 == 1)
            color = GREEN if (i % 2 == 0) else WOOD1
            # create triangle
            if is_up:
                self.canvas.create_polygon(x0, BOARD_H, x1, BOARD_H, (x0 + x1) / 2, BOARD_H - 200, fill=color, outline=BLACK)
            else:
                self.canvas.create_polygon(x0, 0, x1, 0, (x0 + x1) / 2, 200, fill=color, outline=BLACK)
            # draw point number on small band
            self.canvas.create_text((x0 + x1) / 2, BOARD_H - 6 if is_up else 6, text=str(i), fill=BLACK,
                                    font=("Consolas", 9))

        # draw checkers on points stacking
        for i in range(1, 25):
            x0 = MARGIN + (i - 1) * POINT_W
            x1 = x0 + POINT_W
            center_x = (x0 + x1) / 2
            # white stack on top area (upward triangle drawn bottom-up)
            wcount = self.state.points[i].white
            bcount = self.state.points[i].black
            # draw white starting from bottom going up (so they sit on top of triangle)
            for s in range(wcount):
                cy = BOARD_H - 20 - s * 26
                self.draw_checker(center_x, cy, WHITE, shadow=True)
            # draw black starting from top down
            for s in range(bcount):
                cy = 20 + s * 26
                self.draw_checker(center_x, cy, BLACK, shadow=True)

        # draw bar and numbers
        self.canvas.create_rectangle(BOARD_W/2 - 20, BOARD_H/3, BOARD_W/2 + 20, BOARD_H*2/3, fill="#553311", outline="")
        self.canvas.create_text(BOARD_W/2, BOARD_H/2 - 20, text=f"BAR", fill="#FFF", font=("Consolas", 10))
        self.canvas.create_text(BOARD_W/2, BOARD_H/2, text=f"W:{self.state.bar_white}  B:{self.state.bar_black}", fill="#FFF", font=("Consolas", 12))

        # show borne off
        self.canvas.create_text(BOARD_W - 60, BOARD_H/2 - 40, text=f"White off: {self.state.off_white}", font=("Consolas", 11), fill=WHITE)
        self.canvas.create_text(BOARD_W - 60, BOARD_H/2 - 20, text=f"Black off: {self.state.off_black}", font=("Consolas", 11), fill=BLACK)

        # highlight selected point
        if self.state.selected_point:
            i = self.state.selected_point
            x0 = MARGIN + (i - 1) * POINT_W
            x1 = x0 + POINT_W
            self.canvas.create_rectangle(x0, 0, x1, BOARD_H, outline=HIGHLIGHT, width=3)

        # draw dice near top-right area of board
        dice_text = "Dice: " + (", ".join(str(d) for d in self.state.dice) if self.state.dice else "None")
        self.canvas.create_text(BOARD_W - 120, 20, text=dice_text, font=("Consolas", 12), fill="#FFF")

    def draw_checker(self, cx, cy, color, r=12, shadow=True):
        if shadow:
            self.canvas.create_oval(cx - r + 3, cy - r + 3, cx + r + 3, cy + r + 3, fill=CHECKER_SHADOW, outline="")
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="black")

    def update_info(self):
        s = f"Turn: {self.state.turn.upper()}\n"
        s += f"AI mode: {self.ai_mode}\n"
        s += f"Dice: {self.state.dice}\n"
        s += f"Moves remaining: {self.state.moves_remaining}\n"
        s += f"Your off: {self.state.off_white}\nAI off: {self.state.off_black}\n"
        if self.state.turn == 'white' and self.state.moves_remaining:
            s += "Click a white checker to select and then click a target point to move.\n"
        if self.state.game_over:
            s += "Game Over!\n"
        self.info_text['text'] = s

    def check_for_end_and_promote(self):
        # If no white or no black on board -> end
        if self.state.off_white >= 15:
            messagebox.showinfo("Result", "Congratulations — you (White) won!")
            self.state.game_over = True
        if self.state.off_black >= 15:
            messagebox.showinfo("Result", "AI (Black) won.")
            self.state.game_over = True

    def periodic_check(self):
        # called periodically
        self.check_for_end_and_promote()
        self.update_info()
        self.draw_everything()
        self.root.after(600, self.periodic_check)


def check_game_end(state):
    if state.off_white >= 15:
        state.game_over = True
    if state.off_black >= 15:
        state.game_over = True

# -----------------------
# Run application
# -----------------------
def main():
    root = tk.Tk()
    root.geometry(f"{WINDOW_W}x{WINDOW_H}")
    app = SmartGammonUI(root)
    root.after(600, app.periodic_check)
    root.mainloop()

if __name__ == "__main__":
    main()
