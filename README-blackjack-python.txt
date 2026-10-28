# Blackjack Shoe — Python desktop version

## Requirements
- Python 3.10 or newer
- Tkinter (included with most Python installers; on some Linux distributions install `python3-tk`)

## Run
```bash
python blackjack_shoe.py
```

The app is offline and uses virtual money only. It has a finite multi-deck shoe, Hi-Lo running count and true count, manual shuffle, reset bank, automatic reshuffling between hands, and an approximate basic-strategy adviser.

## Notes
- Default settings: six decks, £1,000 virtual bank, £10 bet, 75% penetration.
- Use **Apply settings** to apply a new deck count or starting bank.
- **Reset Bank** changes only the bank; it does not shuffle or reset counts.
- **Shuffle Shoe** resets the shoe and both counts.
- This is a starter implementation. Pair splitting is not yet implemented, and the basic-strategy adviser is an approximation rather than a fully validated chart for every ruleset. Use it for experimentation, not as a certified strategy reference.

# Staking simulator (staking_sim.py)

Tests betting systems that change the stake by Hi-Lo true count, using the
same basic strategy and rules as BlackjackShoe-Preview.html. Every system is
run over the same hands, so only the bet sizes differ.

```bash
python staking_sim.py                      # 1,000,000 hands (about 10 seconds)
python staking_sim.py --hands 3000000      # more hands = smaller margin of error
python staking_sim.py --decks 8 --pen 80 --h17 --peek
python staking_sim.py --help               # all options
```

To try your own betting ramp, edit the SYSTEMS list at the top of the file.
Each step is (true count, units). Every hand is bet at least 1 unit (the
--unit table minimum, default £10); add --allow-sit-out to let 0 units skip a hand.
