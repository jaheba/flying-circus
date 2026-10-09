# Bootstrap half-year outcomes from a fixed history of daily returns (basis points).
HISTORY = [-125, 43, 67, -82, 115, 24, -37, 91, -204, 156, 12, 38,
           -61, 73, 49, -18, 104, -93, 27, 58, -142, 86, 31, -45]
SCENARIOS = 2048
TRADING_DAYS = 126
INITIAL_CENTS = 10000000


def simulate():
    state = 1729
    outcomes = []
    for _ in range(SCENARIOS):
        value = INITIAL_CENTS
        for _ in range(TRADING_DAYS):
            state = (state * 48271) % 2147483647
            daily_return = HISTORY[state % len(HISTORY)]
            value = value * (10000 + daily_return) // 10000
        outcomes.append(value)
    outcomes.sort()
    lower_tail = outcomes[:SCENARIOS // 20]
    print('scenarios: ' + str(len(outcomes)))
    print('p05_cents: ' + str(outcomes[SCENARIOS // 20]))
    print('median_cents: ' + str(outcomes[SCENARIOS // 2]))
    print('p95_cents: ' + str(outcomes[SCENARIOS * 19 // 20]))
    print('lower_tail_mean_cents: ' + str(sum(lower_tail) // len(lower_tail)))
    print('loss_scenarios: ' + str(sum(1 for value in outcomes if value < INITIAL_CENTS)))


simulate()
