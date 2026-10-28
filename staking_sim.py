#!/usr/bin/env python3
"""
Blackjack staking simulator
===========================

Plays a large number of hands using the same basic strategy and table rules
as BlackjackShoe-Preview.html, keeps a Hi-Lo count, then tests several
betting systems ("staking systems") that change the bet based on the TRUE COUNT.

How it works
------------
1. Basic strategy decides every move (hit / stand / double / split).
2. Each hand is recorded with the true count at the moment the bet was placed
   and its result per 1 unit staked (e.g. +1 win, +1.5 blackjack, -2 lost double).
3. Every staking system is applied to the SAME sequence of hands, so the
   comparison is fair: only the bet sizes differ, not the luck of the cards.

Run
---
    python staking_sim.py                       # 1,000,000 hands, default rules
    python staking_sim.py --hands 200000        # quicker run
    python staking_sim.py --decks 8 --pen 80 --h17
    python staking_sim.py --bank 1000 --unit 10 --session 1000

Edit the SYSTEMS list below to try your own betting ramps.

Practice / research tool only. No real money involved.
"""

import argparse
import math
import random
import sys
import time
from array import array

# ---------------------------------------------------------------------------
# STAKING SYSTEMS — edit these!
#
# Each system is a list of (true_count, units) steps. The bet is the units
# from the highest step whose true count is <= the current true count.
# The true count is rounded DOWN (e.g. +2.7 counts as +2, -0.4 counts as -1).
#
# 1 unit = the table minimum (--unit, default £10). Every hand is bet at least
# 1 unit, like a real casino where you must keep betting to keep your seat.
# (Run with --allow-sit-out to let a 0-unit step mean "skip this hand".)
# ---------------------------------------------------------------------------
SYSTEMS = [
    ("Flat £10",                  [(-99, 1)]),
    ("Ramp 1-2 (gentle)",         [(-99, 1), (2, 2)]),
    ("Ramp 1-4",                  [(-99, 1), (2, 2), (3, 3), (4, 4)]),
    ("Ramp 1-6",                  [(-99, 1), (2, 2), (3, 3), (4, 4), (5, 6)]),
    ("Ramp 1-8",                  [(-99, 1), (2, 2), (3, 4), (4, 6), (5, 8)]),
    ("Ramp 1-12",                 [(-99, 1), (2, 2), (3, 4), (4, 8), (5, 12)]),
    ("Units = true count (max 10)", [(-99, 1)] + [(tc, tc) for tc in range(2, 11)]),
    ("Jump: 4 at +2, 8 at +4",    [(-99, 1), (2, 4), (4, 8)]),
]

HIT, STAND, DOUBLE, SPLIT = "H", "S", "D", "P"


# ---------------------------------------------------------------------------
# Cards and counting. Cards are stored as their blackjack value: 2-10, Ace = 11.
# ---------------------------------------------------------------------------
def hilo(card):
    if card <= 6:
        return 1
    if card >= 10:
        return -1
    return 0


def hand_value(cards):
    total = sum(cards)
    aces = cards.count(11)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total, aces > 0


# ---------------------------------------------------------------------------
# Basic strategy — mirrors advice() in BlackjackShoe-Preview.html
# ---------------------------------------------------------------------------
def decide(cards, d, can_split, h17):
    """d = dealer upcard value (2-11). Returns H, S, D or P."""
    total, soft = hand_value(cards)
    two = len(cards) == 2
    fallback = HIT

    if two and can_split and cards[0] == cards[1]:
        r = cards[0]
        if r in (11, 8):
            return SPLIT
        if r == 9 and d in (2, 3, 4, 5, 6, 8, 9):
            return SPLIT
        if r == 7 and 2 <= d <= 7:
            return SPLIT
        if r == 6 and 2 <= d <= 6:
            return SPLIT
        if r in (2, 3) and 2 <= d <= 7:
            return SPLIT
        # Otherwise the pair is played as a normal total (10s, 5s, 4s, etc.)

    if soft:
        if total >= 19:
            move = STAND
        elif total == 18:
            if 3 <= d <= 6:
                move, fallback = DOUBLE, STAND
            elif d in (2, 7, 8):
                move = STAND
            else:
                move = HIT
        elif total == 17 and 3 <= d <= 6:
            move = DOUBLE
        elif total in (15, 16) and 4 <= d <= 6:
            move = DOUBLE
        elif total in (13, 14) and 5 <= d <= 6:
            move = DOUBLE
        else:
            move = HIT
    else:
        if total >= 17:
            move = STAND
        elif total >= 13:
            move = STAND if 2 <= d <= 6 else HIT
        elif total == 12:
            move = STAND if 4 <= d <= 6 else HIT
        elif total == 11:
            move = HIT if (d == 11 and h17) else DOUBLE
        elif total == 10:
            move = DOUBLE if 2 <= d <= 9 else HIT
        elif total == 9:
            move = DOUBLE if 3 <= d <= 6 else HIT
        else:
            move = HIT

    if move == DOUBLE and not two:
        move = fallback
    return move


# ---------------------------------------------------------------------------
# The shoe and one round of play
# ---------------------------------------------------------------------------
class Shoe:
    def __init__(self, decks, pen, rng):
        self.decks, self.pen, self.rng = decks, pen, rng
        self.shuffle()

    def shuffle(self):
        one_deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
        self.cards = one_deck * self.decks
        self.rng.shuffle(self.cards)
        self.running = 0
        self.shuffles = getattr(self, "shuffles", -1) + 1

    def draw(self):
        if not self.cards:  # ran out mid-hand (rare)
            self.shuffle()
        c = self.cards.pop()
        self.running += hilo(c)
        return c

    def needs_shuffle(self):
        dealt = 1 - len(self.cards) / (self.decks * 52)
        return dealt >= self.pen

    def true_count(self):
        decks_left = max(len(self.cards) / 52, 0.25)
        return self.running / decks_left


def play_round(shoe, h17, peek):
    """Plays one hand with a 1-unit bet. Returns the net result in units."""
    player = [shoe.draw(), shoe.draw()]
    dealer = [shoe.draw(), shoe.draw()]  # hole card is counted here; it is seen by the end
    up = dealer[0]
    dealer_bj = hand_value(dealer)[0] == 21
    player_bj = hand_value(player)[0] == 21

    if player_bj:
        return 0.0 if dealer_bj else 1.5
    if peek and dealer_bj:            # US style: dealer checks first, you only lose 1 unit
        return -1.0

    hands = [player]
    stakes = [1.0]
    split_done = False
    i = 0
    while i < len(hands):
        h = hands[i]
        while True:
            total, _ = hand_value(h)
            if total >= 21:
                break
            move = decide(h, up, can_split=(not split_done and len(h) == 2), h17=h17)
            if move == SPLIT:
                split_done = True
                second = [h.pop()]
                h.append(shoe.draw())
                second.append(shoe.draw())
                hands.append(second)
                stakes.append(1.0)
                continue
            if move == DOUBLE:
                stakes[i] *= 2
                h.append(shoe.draw())
                break
            if move == STAND:
                break
            h.append(shoe.draw())
        i += 1

    # Dealer always plays out (same as the web game)
    while True:
        dt, ds = hand_value(dealer)
        if dt < 17 or (dt == 17 and ds and h17):
            dealer.append(shoe.draw())
        else:
            break
    dt = hand_value(dealer)[0]

    net = 0.0
    for h, s in zip(hands, stakes):
        pt = hand_value(h)[0]
        if pt > 21:
            net -= s
        elif dealer_bj:               # no peek: dealer blackjack takes doubles and splits too
            net -= s
        elif dt > 21 or pt > dt:
            net += s
        elif pt < dt:
            net -= s
    return net


def simulate(n_hands, decks, pen, h17, peek, seed):
    rng = random.Random(seed)
    shoe = Shoe(decks, pen, rng)
    tcs = array("b")       # true count (rounded down) when the bet was placed
    results = array("d")   # net result per 1 unit staked
    step = max(n_hands // 20, 1)
    start = time.time()
    for n in range(n_hands):
        if shoe.needs_shuffle():
            shoe.shuffle()
        tc = math.floor(shoe.true_count())
        tcs.append(max(-20, min(20, tc)))
        results.append(play_round(shoe, h17, peek))
        if (n + 1) % step == 0:
            pct = (n + 1) / n_hands * 100
            sys.stderr.write(f"\r  Simulating... {pct:5.1f}%  ({time.time() - start:.0f}s)")
    sys.stderr.write("\r" + " " * 50 + "\r")
    return tcs, results, shoe.shuffles


# ---------------------------------------------------------------------------
# Applying staking systems
# ---------------------------------------------------------------------------
def make_bet_table(steps, min_units):
    steps = sorted(steps)
    table = {}
    for tc in range(-20, 21):
        units = 0
        for threshold, u in steps:
            if tc >= threshold:
                units = u
        table[tc] = max(units, min_units)
    return table


def evaluate(tcs, results, steps, unit, bank, session_len, min_units):
    bets = make_bet_table(steps, min_units)
    n = len(results)

    # Whole run as one long session (unlimited bankroll)
    played = wagered = 0
    net = sum_sq = 0.0
    peak = low_dd = 0.0
    for tc, r in zip(tcs, results):
        b = bets[tc]
        if b == 0:
            continue
        played += 1
        wagered += b
        win = b * r
        net += win
        sum_sq += win * win
        if net > peak:
            peak = net
        if net - peak < low_dd:
            low_dd = net - peak

    mean = net / n                       # per hand dealt (sitting out counts as 0)
    var = sum_sq / n - mean * mean
    sd = math.sqrt(max(var, 0.0))

    # Split the run into casino sessions. For each one, track the lowest point
    # (how far below your starting bank you fell) and where you finished.
    bank_units = bank / unit
    sessions = busted = ahead = 0
    finals, lows = [], []
    for start in range(0, n - session_len + 1, session_len):
        s_net = low = 0.0
        broke = False
        for k in range(start, start + session_len):
            want = bets[tcs[k]]
            if want == 0:
                continue
            if bank_units + s_net < want:  # can't cover this bet any more
                broke = True
            s_net += want * results[k]
            if s_net < low:
                low = s_net
        sessions += 1
        lows.append(-low)
        if broke:
            busted += 1
            finals.append(0.0)
        else:
            finals.append(bank_units + s_net)
            ahead += s_net > 0
    lows.sort()
    finals.sort()

    def pct(xs, p):
        return xs[min(len(xs) - 1, int(len(xs) * p))] if xs else float("nan")

    max_bet = max(bets.values())
    return {
        "bet_range": f"£{min(bets.values()) * unit:g}-£{max_bet * unit:g}",
        "played": played,
        "avg_bet": (wagered / played) * unit if played else 0,
        "wagered": wagered * unit,
        "net": net * unit,
        "per100": mean * 100 * unit,
        "per100_err": 1.96 * sd * 100 / math.sqrt(n) * unit,
        "edge": (net / wagered * 100) if wagered else 0,
        "sd100": sd * 10 * unit,
        "drawdown": -low_dd * unit,
        "sessions": sessions,
        "ruin": (busted / sessions * 100) if sessions else float("nan"),
        "ahead": (ahead / sessions * 100) if sessions else float("nan"),
        "median_end": pct(finals, 0.5) * unit,
        # Bank that covers the deepest dip (plus your biggest bet) in 95% of sessions
        "bank95": math.ceil((pct(lows, 0.95) + max_bet) * unit / 100) * 100,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def money(x):
    sign = "-" if x < 0 else ""
    return f"{sign}£{abs(x):,.0f}"


def print_edge_by_count(tcs, results):
    print("\nPLAYER EDGE BY TRUE COUNT (flat 1-unit bets)")
    print("  How good each true count is for you. Positive = you have the edge.")
    print(f"  {'True count':>10}  {'% of hands':>10}  {'Your edge':>10}  {'± (95%)':>8}")
    buckets = {}
    for tc, r in zip(tcs, results):
        key = max(-4, min(6, tc))
        s = buckets.setdefault(key, [0, 0.0, 0.0])
        s[0] += 1
        s[1] += r
        s[2] += r * r
    n = len(results)
    for key in sorted(buckets):
        c, total, sq = buckets[key]
        m = total / c
        sd = math.sqrt(max(sq / c - m * m, 0))
        label = f"<= {key}" if key == -4 else (f">= +{key}" if key == 6 else f"{key:+d}")
        print(f"  {label:>10}  {c / n * 100:9.1f}%  {m * 100:+9.2f}%  {1.96 * sd / math.sqrt(c) * 100:7.2f}%")


def main():
    p = argparse.ArgumentParser(description="Test blackjack staking systems driven by the Hi-Lo true count.")
    p.add_argument("--hands", type=int, default=1_000_000, help="hands to simulate (default 1,000,000)")
    p.add_argument("--decks", type=int, default=6, help="decks in the shoe (default 6)")
    p.add_argument("--pen", type=float, default=75, help="shuffle after this %% of the shoe is dealt (default 75)")
    p.add_argument("--h17", action="store_true", help="dealer hits soft 17 (default: stands)")
    p.add_argument("--peek", action="store_true",
                   help="dealer checks for blackjack first, so you only lose 1 unit to it (default: no peek, like the web game)")
    p.add_argument("--unit", type=float, default=10, help="£ per betting unit (default 10)")
    p.add_argument("--bank", type=float, default=1000, help="£ starting bank per session (default 1000)")
    p.add_argument("--session", type=int, default=1000, help="hands per session for the risk-of-ruin test (default 1000)")
    p.add_argument("--seed", type=int, default=None, help="random seed, to repeat a run exactly")
    p.add_argument("--allow-sit-out", action="store_true",
                   help="let 0-unit steps skip a hand (default: always bet at least 1 unit)")
    a = p.parse_args()
    min_units = 0 if a.allow_sit_out else 1

    rules = (f"{a.decks} decks, shuffle at {a.pen:g}%, dealer {'hits' if a.h17 else 'stands on'} soft 17, "
             f"{'dealer peeks' if a.peek else 'no peek (lose doubles/splits to dealer blackjack)'}, blackjack pays 3:2")
    print("BLACKJACK STAKING SIMULATOR")
    print(f"  Rules: {rules}")
    print(f"  Minimum bet: £{a.unit:g} {'(sitting out allowed)' if a.allow_sit_out else 'on every hand'}   "
          f"Session bank: £{a.bank:,.0f}   Session length: {a.session:,} hands")
    print(f"  Simulating {a.hands:,} hands...")

    t0 = time.time()
    tcs, results, shuffles = simulate(a.hands, a.decks, a.pen / 100, a.h17, a.peek, a.seed)
    print(f"  Done in {time.time() - t0:.0f}s ({shuffles:,} shuffles).")

    print_edge_by_count(tcs, results)

    print("\nSTAKING SYSTEMS (same cards for every system)")
    rows = []
    for name, steps in SYSTEMS:
        rows.append((name, evaluate(tcs, results, steps, a.unit, a.bank, a.session, min_units)))

    hdr = (f"  {'System':<28} {'Bets':>10} {'Avg bet':>8} {'Win per 100 hands':>18} {'Edge':>7} "
           f"{'Swing/100':>10} {'Ahead':>6} {'Broke':>6} {'Median end':>11} {'Bank needed':>12}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for name, r in rows:
        win = f"{money(r['per100'])} ±{money(r['per100_err'])}"
        print(f"  {name:<28} {r['bet_range']:>10} {money(r['avg_bet']):>8} {win:>18} {r['edge']:+6.2f}% "
              f"{money(r['sd100']):>10} {r['ahead']:5.0f}% {r['ruin']:5.1f}% {money(r['median_end']):>11} "
              f"{money(r['bank95']):>12}")

    print(f"""
WHAT THE COLUMNS MEAN
  Bets               Smallest and biggest stake the system uses.
  Avg bet            Average stake per hand.
  Win per 100 hands  Average profit (or loss) per 100 hands. The ± is the 95%
                     margin of error: if it is bigger than the number itself,
                     the result could just be luck. Run more hands to shrink it.
  Edge               Profit as a % of all the money you staked.
  Swing/100          Typical up-or-down swing over 100 hands (1 standard deviation).
  Ahead              % of {a.session:,}-hand sessions you finished in profit.
  Broke              % of sessions where a £{a.bank:,.0f} bank ran out.
  Median end         Typical bank at the end of a session (started at £{a.bank:,.0f}).
  Bank needed        Bank that would have lasted 95% of {a.session:,}-hand sessions.

Notes: the true count here is exact (cards left ÷ 52). At a real table you'd
estimate decks left by eye, so real results are a bit worse. Casinos also watch
for big jumps in bet size. Research and practice only.""")


if __name__ == "__main__":
    main()
