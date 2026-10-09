# Choose indivisible projects that maximize benefit within an engineering-day budget.
PROJECTS = 80
BUDGET_DAYS = 2400


def allocate(projects, budget):
    previous = [0] * (budget + 1)
    decisions = []
    for cost, benefit in projects:
        current = previous.copy()
        chosen = [False] * (budget + 1)
        for available in range(cost, budget + 1):
            candidate = previous[available - cost] + benefit
            if candidate > current[available]:
                current[available] = candidate
                chosen[available] = True
        decisions.append(chosen)
        previous = current
    remaining = budget
    selected = []
    for index in range(len(projects) - 1, -1, -1):
        if decisions[index][remaining]:
            selected.append(index)
            remaining -= projects[index][0]
    selected.reverse()
    return previous[budget], selected


def plan():
    projects = [(20 + (index * 37 + 11) % 181, 100 + (index * 97 + 53) % 901)
                for index in range(PROJECTS)]
    benefit, selected = allocate(projects, BUDGET_DAYS)
    cost = sum(projects[index][0] for index in selected)
    assert cost <= BUDGET_DAYS
    assert benefit == sum(projects[index][1] for index in selected)
    print('benefit: ' + str(benefit))
    print('days: ' + str(cost))
    print('projects: ' + str(len(selected)))
    print('selected: ' + ','.join(str(index) for index in selected))


plan()
