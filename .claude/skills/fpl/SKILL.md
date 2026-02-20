---
name: fpl
description: FPL domain expert. Use when questions involve Fantasy Premier League rules, scoring, strategy, transfer mechanics, chip usage, or data interpretation.
---

# FPL Domain Expert

Answer FPL questions with precision. Reference our schema conventions.

## Scoring System (2024/25)
- **Appearance**: 1pt (1-59 min), 2pt (60+ min)
- **Goals**: GKP/DEF=6, MID=5, FWD=4
- **Assists**: 3pt
- **Clean sheets**: GKP/DEF=4, MID=1, FWD=0
- **Saves**: GKP 1pt per 3 saves
- **Penalties saved**: 5pt; missed: -2pt
- **Bonus**: 1-3pt to top 3 BPS scorers per match
- **Cards**: Yellow=-1, Red=-3
- **Own goals**: -2pt

## Transfer Rules
- 1 free transfer per GW, max 5 banked (2024/25 rule change)
- Extra transfers cost **4 points each**
- Selling price = purchase price + floor(50% of profit)
- Transfer deadline = gameweek deadline_time in our schema

## Chips (one per season unless noted)
- **Wildcard**: Unlimited free transfers for 1 GW. Two per season (1 before GW20, 1 after)
- **Free Hit**: Unlimited transfers for 1 GW, squad resets after
- **Bench Boost**: Bench players score points for 1 GW
- **Triple Captain**: Captain gets 3x points for 1 GW

## Squad Rules
- 15 players: 2 GKP, 5 DEF, 5 MID, 3 FWD
- Max 3 players from any single team
- Budget: £100.0m
- Slots 1-11 = starting XI, 12-15 = bench (auto-sub priority order)
- `multiplier`: 0=benched, 1=playing, 2=captain, 3=triple captain

## Key Metrics
- **Form**: Rolling average points over recent GWs
- **ICT Index**: Influence + Creativity + Threat (composite)
- **xG/xA/xGI**: Expected goals/assists/goal involvements (statistical model)
- **BPS**: Bonus Points System raw score (determines 1-3 bonus allocation)
- **FDR**: Fixture Difficulty Rating 1-5 (1=easiest, 5=hardest)
- **Points per million**: total_points / price (value metric)
- **Effective ownership**: % of active managers who own a player

## Player Status Codes
- `a` = available
- `i` = injured (red flag)
- `d` = doubtful (yellow flag, 50/50)
- `s` = suspended
- `u` = unavailable (left club, etc.)

## Our Schema Conventions
- **Price**: Stored in millions as decimal (13.2 = £13.2m)
- **manager_id / league_id**: Integers from FPL API, NOT UUIDs
- **player_id, team_id, position_id**: UUID FKs to our tables
- **gameweek**: Integer 1-38, not "event"
- **web_name**: Display name (e.g., "Salah"), not full name

## Common Analysis Patterns
- **Fixture planning**: Look 3-5 GWs ahead, avg FDR per team
- **Differential**: Player in your squad but not rival's (or vice versa)
- **Template**: Players owned by >30% = template; <5% = punt
- **Rotation risk**: avg minutes < 60 per GW
- **Price rise indicator**: High net transfers in (transfers_in_event >> transfers_out_event)
