#!/usr/bin/env python3
"""
Blackjack Shoe — offline desktop practice simulator
Python 3.10+ recommended. Uses only the Python standard library (Tkinter).

Features:
- Finite multi-deck shoe; exposed cards are removed until shuffle
- Hi-Lo running count and true count
- Manual shuffle and reset-bank controls
- Automatic reshuffle between hands at configured penetration
- Virtual bank and adjustable bet
- Basic-strategy advice (common multi-deck, dealer stands on soft 17,
  double after split allowed). This is a practical starter chart, not a
  certified strategy engine for every possible table rule.
"""

import random
import tkinter as tk
from tkinter import ttk, messagebox

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
HI_LO = {"2": 1, "3": 1, "4": 1, "5": 1, "6": 1,
         "7": 0, "8": 0, "9": 0,
         "10": -1, "J": -1, "Q": -1, "K": -1, "A": -1}
CARD_VALUE = {"A": 11, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
              "7": 7, "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10}


def hand_total(cards):
    total = sum(CARD_VALUE[c[0]] for c in cards)
    aces = sum(1 for c in cards if c[0] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    soft = any(c[0] == "A" for c in cards) and total <= 21 and (
        sum(CARD_VALUE[c[0]] for c in cards) == total
    )
    # More reliable soft check: one Ace can still count as 11.
    raw = sum(CARD_VALUE[c[0]] for c in cards)
    soft = any(c[0] == "A" for c in cards) and raw == total
    return total, soft


def fmt_card(card):
    rank, suit = card
    return f"{rank}{suit}"


def basic_strategy(player, dealer_up, can_double=True, can_split=True):
    """Compact common multi-deck basic strategy approximation."""
    total, soft = hand_total(player)
    up = dealer_up[0]
    dealer = 11 if up == "A" else (10 if up in ("10", "J", "Q", "K") else int(up))
    pair = len(player) == 2 and player[0][0] == player[1][0]
    rank = player[0][0] if pair else None

    if pair and can_split:
        if rank == "A" or rank == "8":
            return "SPLIT"
        if rank in ("10", "J", "Q", "K"):
            return "STAND"
        if rank == "9":
            return "SPLIT" if dealer in (2, 3, 4, 5, 6, 8, 9) else "STAND"
        if rank == "7":
            return "SPLIT" if 2 <= dealer <= 7 else "HIT"
        if rank == "6":
            return "SPLIT" if 2 <= dealer <= 6 else "HIT"
        if rank in ("2", "3"):
            return "SPLIT" if 2 <= dealer <= 7 else "HIT"
        if rank == "4":
            return "SPLIT" if dealer in (5, 6) else "HIT"
        if rank == "5":
            pass  # treat as hard 10

    if soft:
        if total >= 19:
            return "STAND"
        if total == 18:
            if dealer in (3, 4, 5, 6) and can_double:
                return "DOUBLE"
            if dealer in (2, 7, 8):
                return "STAND"
            return "HIT"
        if total == 17:
            return "DOUBLE" if can_double and 3 <= dealer <= 6 else "HIT"
        if total in (15, 16):
            return "DOUBLE" if can_double and 4 <= dealer <= 6 else "HIT"
        if total in (13, 14):
            return "DOUBLE" if can_double and 5 <= dealer <= 6 else "HIT"

    # Hard totals
    if total <= 8:
        return "HIT"
    if total == 9:
        return "DOUBLE" if can_double and 3 <= dealer <= 6 else "HIT"
    if total == 10:
        return "DOUBLE" if can_double and dealer <= 9 else "HIT"
    if total == 11:
        return "DOUBLE" if can_double and dealer != 11 else "HIT"
    if total == 12:
        return "STAND" if 4 <= dealer <= 6 else "HIT"
    if 13 <= total <= 16:
        return "STAND" if 2 <= dealer <= 6 else "HIT"
    return "STAND"


class BlackjackApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Blackjack Shoe — Practice")
        self.root.geometry("900x760")
        self.root.minsize(760, 650)

        self.decks_var = tk.IntVar(value=6)
        self.bank_start_var = tk.IntVar(value=1000)
        self.bet_var = tk.IntVar(value=10)
        self.penetration_var = tk.IntVar(value=75)
        self.show_count_var = tk.BooleanVar(value=True)
        self.show_advice_var = tk.BooleanVar(value=True)

        self.bank = 1000
        self.running_count = 0
        self.shoe = []
        self.discards = []
        self.hand_player = []
        self.hand_dealer = []
        self.phase = "ready"
        self.current_bet = 10
        self.can_double = True
        self.can_split = True
        self.message = "Ready to deal. Choose your bet, then press Deal."
        self.last_result = ""
        self.shuffle_shoe()

        self._build_ui()
        self.update_ui()

    def _build_ui(self):
        self.root.configure(bg="#154f3d")
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", font=("Arial", 12, "bold"), padding=9)
        style.configure("TLabel", font=("Arial", 11))
        style.configure("Header.TLabel", font=("Arial", 17, "bold"))
        style.configure("Card.TLabel", font=("Arial", 20, "bold"), padding=10,
                        background="white", foreground="#18231f")
        style.configure("Advice.TLabel", font=("Arial", 12, "bold"),
                        background="#f4e5b8", foreground="#493a14", padding=10)

        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="BLACKJACK SHOE", style="Header.TLabel").pack(side="left")
        self.bank_label = ttk.Label(header, text="Virtual bank: £1,000", style="Header.TLabel")
        self.bank_label.pack(side="right")

        controls = ttk.LabelFrame(outer, text="Table settings", padding=10)
        controls.pack(fill="x", pady=(0, 10))
        ttk.Label(controls, text="Decks").grid(row=0, column=0, sticky="w", padx=4)
        ttk.Combobox(controls, textvariable=self.decks_var, values=(1, 2, 4, 6, 8),
                     width=5, state="readonly").grid(row=0, column=1, padx=4)
        ttk.Label(controls, text="Starting bank (£)").grid(row=0, column=2, sticky="w", padx=4)
        ttk.Entry(controls, textvariable=self.bank_start_var, width=9).grid(row=0, column=3, padx=4)
        ttk.Label(controls, text="Bet (£)").grid(row=0, column=4, sticky="w", padx=4)
        ttk.Spinbox(controls, from_=1, to=100000, increment=5, textvariable=self.bet_var,
                    width=8).grid(row=0, column=5, padx=4)
        ttk.Label(controls, text="Auto shuffle (%)").grid(row=0, column=6, sticky="w", padx=4)
        ttk.Combobox(controls, textvariable=self.penetration_var,
                     values=(50, 60, 65, 70, 75, 80), width=5,
                     state="readonly").grid(row=0, column=7, padx=4)
        ttk.Button(controls, text="Apply settings", command=self.apply_settings).grid(
            row=0, column=8, padx=8)

        counts = ttk.Frame(outer)
        counts.pack(fill="x", pady=(0, 10))
        self.running_label = ttk.Label(counts, text="Running count: 0", style="Header.TLabel")
        self.running_label.pack(side="left", padx=(0, 22))
        self.true_label = ttk.Label(counts, text="True count: 0.0", style="Header.TLabel")
        self.true_label.pack(side="left", padx=(0, 22))
        self.decks_left_label = ttk.Label(counts, text="Decks left: 6.0")
        self.decks_left_label.pack(side="left")
        self.pen_label = ttk.Label(counts, text="Penetration: 0%")
        self.pen_label.pack(side="right")

        table = tk.Frame(outer, bg="#176147", bd=2, relief="ridge")
        table.pack(fill="both", expand=True, pady=(0, 10))
        self.dealer_title = tk.Label(table, text="DEALER", bg="#176147", fg="#e7f3ec",
                                     font=("Arial", 12, "bold"))
        self.dealer_title.pack(pady=(12, 0))
        self.dealer_cards_frame = tk.Frame(table, bg="#176147")
        self.dealer_cards_frame.pack(pady=6)
        self.dealer_total_label = tk.Label(table, text="", bg="#176147", fg="white",
                                           font=("Arial", 11))
        self.dealer_total_label.pack()
        self.player_title = tk.Label(table, text="YOUR HAND", bg="#176147", fg="#e7f3ec",
                                     font=("Arial", 12, "bold"))
        self.player_title.pack(pady=(18, 0))
        self.player_cards_frame = tk.Frame(table, bg="#176147")
        self.player_cards_frame.pack(pady=6)
        self.player_total_label = tk.Label(table, text="", bg="#176147", fg="white",
                                           font=("Arial", 11))
        self.player_total_label.pack()
        self.status_label = tk.Label(table, text=self.message, bg="#176147", fg="white",
                                     font=("Arial", 12), wraplength=760)
        self.status_label.pack(fill="x", padx=12, pady=10)

        self.advice_label = ttk.Label(outer, text="Strategy recommendation will appear here.",
                                      style="Advice.TLabel", anchor="w", wraplength=850)
        self.advice_label.pack(fill="x", pady=(0, 10))

        action_row = ttk.Frame(outer)
        action_row.pack(fill="x", pady=(0, 8))
        self.deal_btn = ttk.Button(action_row, text="DEAL / NEXT HAND", command=self.deal_or_next)
        self.deal_btn.pack(side="left", fill="x", expand=True, padx=3)
        self.hit_btn = ttk.Button(action_row, text="HIT", command=self.hit, state="disabled")
        self.hit_btn.pack(side="left", fill="x", expand=True, padx=3)
        self.stand_btn = ttk.Button(action_row, text="STAND", command=self.stand, state="disabled")
        self.stand_btn.pack(side="left", fill="x", expand=True, padx=3)
        self.double_btn = ttk.Button(action_row, text="DOUBLE", command=self.double_down, state="disabled")
        self.double_btn.pack(side="left", fill="x", expand=True, padx=3)
        self.split_btn = ttk.Button(action_row, text="SPLIT", command=self.split_pair, state="disabled")
        self.split_btn.pack(side="left", fill="x", expand=True, padx=3)

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="SHUFFLE SHOE", command=self.manual_shuffle).pack(
            side="left", fill="x", expand=True, padx=3)
        ttk.Button(bottom, text="RESET BANK", command=self.reset_bank).pack(
            side="left", fill="x", expand=True, padx=3)
        ttk.Checkbutton(bottom, text="Show counts", variable=self.show_count_var,
                        command=self.update_ui).pack(side="left", padx=10)
        ttk.Checkbutton(bottom, text="Show strategy advice", variable=self.show_advice_var,
                        command=self.update_ui).pack(side="left", padx=10)

    def make_shoe(self):
        cards = [(rank, suit) for _ in range(self.decks_var.get())
                 for suit in SUITS for rank in RANKS]
        random.shuffle(cards)
        return cards

    def shuffle_shoe(self):
        self.shoe = self.make_shoe()
        self.discards = []
        self.running_count = 0
        self.phase = "ready"
        self.hand_player = []
        self.hand_dealer = []
        self.current_bet = 0
        self.message = f"Fresh {self.decks_var.get()}-deck shoe. Ready to deal."
        self.last_result = ""
        if hasattr(self, "status_label"):
            self.update_ui()

    def manual_shuffle(self):
        if self.phase == "playing":
            if not messagebox.askyesno("Shuffle shoe", "A hand is in progress. Abandon it and shuffle?"):
                return
        self.shuffle_shoe()
        self.update_ui()

    def apply_settings(self):
        try:
            start_bank = int(self.bank_start_var.get())
            bet = int(self.bet_var.get())
            if start_bank < 1 or bet < 1:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid settings", "Bank and bet must be positive whole numbers.")
            return
        self.bank = start_bank
        self.current_bet = 0
        self.shuffle_shoe()
        self.message = "Settings applied. Fresh shoe ready."
        self.update_ui()

    def reset_bank(self):
        try:
            amount = int(self.bank_start_var.get())
            if amount < 1:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid bank", "Enter a positive whole number for the starting bank.")
            return
        self.bank = amount
        self.message = f"Virtual bank reset to £{self.bank:,}. Shoe and counts unchanged."
        self.update_ui()

    def decks_remaining(self):
        return max(len(self.shoe) / 52.0, 1 / 52)

    def true_count(self):
        return self.running_count / self.decks_remaining()

    def penetration(self):
        total = max(1, self.decks_var.get() * 52)
        return 100 * (total - len(self.shoe)) / total

    def expose(self, card):
        self.running_count += HI_LO[card[0]]
        self.discards.append(card)

    def deal_or_next(self):
        if self.phase == "playing":
            return
        if self.phase == "finished":
            if self.penetration() >= self.penetration_var.get():
                self.shuffle_shoe()
            self.phase = "ready"
        if self.bank <= 0:
            messagebox.showinfo("Bank empty", "Your virtual bank is empty. Use Reset Bank to continue.")
            return
        try:
            bet = int(self.bet_var.get())
            if bet < 1:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid bet", "Enter a positive whole-number bet.")
            return
        if bet > self.bank:
            messagebox.showinfo("Bet too large", "Your bet cannot exceed your virtual bank.")
            return
        if len(self.shoe) < 15:
            self.shuffle_shoe()
        self.current_bet = bet
        self.bank -= bet
        self.hand_player = [self.shoe.pop(), self.shoe.pop()]
        self.hand_dealer = [self.shoe.pop(), self.shoe.pop()]
        # Player cards and dealer upcard are exposed; hole card is counted when revealed.
        for c in self.hand_player:
            self.expose(c)
        self.expose(self.hand_dealer[0])
        self.phase = "playing"
        self.message = "Your move. The dealer's hole card is hidden."
        ptotal, _ = hand_total(self.hand_player)
        if ptotal == 21:
            self.finish_player_natural()
        self.update_ui()

    def finish_player_natural(self):
        self.reveal_hole()
        dtotal, _ = hand_total(self.hand_dealer)
        if dtotal == 21:
            self.bank += self.current_bet
            self.message = "Push: both you and dealer have blackjack."
        else:
            # Original wager already removed; return wager plus 3:2 winnings.
            self.bank += self.current_bet * 2.5
            self.message = "Blackjack! Paid 3:2."
        self.phase = "finished"

    def reveal_hole(self):
        if len(self.hand_dealer) >= 2 and self.hand_dealer[1] not in self.discards:
            self.expose(self.hand_dealer[1])

    def hit(self):
        if self.phase != "playing":
            return
        c = self.shoe.pop()
        self.hand_player.append(c)
        self.expose(c)
        total, _ = hand_total(self.hand_player)
        if total > 21:
            self.message = "Bust! You lose this hand."
            self.phase = "finished"
            self.reveal_hole()
        else:
            self.message = "You hit. Choose your next action."
        self.update_ui()

    def stand(self):
        if self.phase != "playing":
            return
        self.reveal_hole()
        while hand_total(self.hand_dealer)[0] < 17:
            c = self.shoe.pop()
            self.hand_dealer.append(c)
            self.expose(c)
        ptotal = hand_total(self.hand_player)[0]
        dtotal = hand_total(self.hand_dealer)[0]
        if dtotal > 21 or ptotal > dtotal:
            self.bank += self.current_bet * 2
            self.message = f"You win. Player {ptotal}, dealer {dtotal}."
        elif ptotal == dtotal:
            self.bank += self.current_bet
            self.message = f"Push. Both have {ptotal}."
        else:
            self.message = f"You lose. Player {ptotal}, dealer {dtotal}."
        self.phase = "finished"
        self.update_ui()

    def double_down(self):
        if self.phase != "playing" or len(self.hand_player) != 2:
            return
        if self.bank < self.current_bet:
            messagebox.showinfo("Bank too low", "Not enough virtual bank to double.")
            return
        self.bank -= self.current_bet
        self.current_bet *= 2
        c = self.shoe.pop()
        self.hand_player.append(c)
        self.expose(c)
        if hand_total(self.hand_player)[0] > 21:
            self.reveal_hole()
            self.message = "Bust after doubling. You lose."
            self.phase = "finished"
            self.update_ui()
        else:
            self.stand()

    def split_pair(self):
        messagebox.showinfo("Split", "Pair splitting is not enabled in this starter version yet. The strategy adviser can still recommend SPLIT.")

    def update_ui(self):
        if not hasattr(self, "status_label"):
            return
        self.bank_label.config(text=f"Virtual bank: £{self.bank:,.2f}")
        self.running_label.config(text=f"Running count: {self.running_count:+d}")
        self.true_label.config(text=f"True count: {self.true_count():+.1f}")
        self.decks_left_label.config(text=f"Decks left: {len(self.shoe)/52:.2f}")
        self.pen_label.config(text=f"Penetration: {self.penetration():.0f}%")

        for frame, cards, is_dealer in (
            (self.dealer_cards_frame, self.hand_dealer, True),
            (self.player_cards_frame, self.hand_player, False),
        ):
            for child in frame.winfo_children():
                child.destroy()
            for i, card in enumerate(cards):
                hidden = is_dealer and self.phase == "playing" and i == 1
                txt = "🂠" if hidden else fmt_card(card)
                color = "#b21e35" if not hidden and card[1] in ("♥", "♦") else "#17231f"
                lbl = tk.Label(frame, text=txt, font=("Arial", 22, "bold"), bg="white",
                               fg=color, width=4, height=2, relief="raised", bd=2)
                lbl.pack(side="left", padx=4, pady=3)

        if self.hand_player:
            pt, _ = hand_total(self.hand_player)
            self.player_total_label.config(text=f"Total: {pt}")
        else:
            self.player_total_label.config(text="")
        if self.hand_dealer:
            shown = self.hand_dealer[:1] if self.phase == "playing" else self.hand_dealer
            dt, _ = hand_total(shown)
            self.dealer_total_label.config(text=f"Showing: {dt}" if self.phase == "playing"
                                           else f"Total: {hand_total(self.hand_dealer)[0]}")
        else:
            self.dealer_total_label.config(text="")
        self.status_label.config(text=self.message)

        advice = "Strategy advice hidden."
        if self.show_advice_var.get() and self.phase == "playing" and self.hand_player:
            action = basic_strategy(self.hand_player, self.hand_dealer[0],
                                    can_double=(len(self.hand_player) == 2 and self.bank >= self.current_bet),
                                    can_split=(len(self.hand_player) == 2 and self.hand_player[0][0] == self.hand_player[1][0]))
            advice = f"Basic-strategy suggestion: {action}. (Common multi-deck approximation; not count deviations.)"
        elif self.show_advice_var.get():
            advice = "Strategy recommendation appears during your turn."
        self.advice_label.config(text=advice)
        self.running_label.pack_forget()
        self.true_label.pack_forget()
        self.decks_left_label.pack_forget()
        self.pen_label.pack_forget()
        if self.show_count_var.get():
            self.running_label.pack(side="left", padx=(0, 22))
            self.true_label.pack(side="left", padx=(0, 22))
            self.decks_left_label.pack(side="left")
            self.pen_label.pack(side="right")

        playing = self.phase == "playing"
        self.hit_btn.config(state="normal" if playing else "disabled")
        self.stand_btn.config(state="normal" if playing else "disabled")
        can_double = playing and len(self.hand_player) == 2 and self.bank >= self.current_bet
        self.double_btn.config(state="normal" if can_double else "disabled")
        can_split = playing and len(self.hand_player) == 2 and self.hand_player[0][0] == self.hand_player[1][0]
        self.split_btn.config(state="normal" if can_split else "disabled")
        self.deal_btn.config(state="disabled" if playing else "normal",
                             text="HAND IN PROGRESS" if playing else "DEAL / NEXT HAND")


def main():
    root = tk.Tk()
    app = BlackjackApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
