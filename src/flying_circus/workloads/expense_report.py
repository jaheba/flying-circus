transactions = [
    {"team": "engineering", "category": "travel", "cents": 12500},
    {"team": "sales", "category": "meals", "cents": 4800},
    {"team": "engineering", "category": "software", "cents": 9900},
    {"team": "sales", "category": "travel", "cents": 22000},
]
transactions.extend([
    {"team": "support", "category": "software", "cents": 4900},
    {"team": "engineering", "category": "meals", "cents": 7200},
    {"team": "support", "category": "travel", "cents": 18350},
    {"team": "sales", "category": "software", "cents": 12900},
])
totals = {}
for transaction in transactions:
    team = transaction["team"]
    totals[team] = totals.get(team, 0) + transaction["cents"]
for team in sorted(totals):
    print(team + ": " + str(totals[team]))
