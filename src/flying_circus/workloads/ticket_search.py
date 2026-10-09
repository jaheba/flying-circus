import math

# Build a TF-IDF index and rank support tickets for incident investigation.
PRODUCTS = ['payments', 'invoices', 'accounts', 'reports', 'exports', 'search', 'webhooks', 'storage']
SYMPTOMS = ['timeout', 'duplicate', 'missing', 'delayed', 'invalid', 'failed', 'slow', 'unavailable']
ACTIONS = ['retry request', 'check permissions', 'restart connection', 'verify configuration',
           'inspect logs', 'update settings', 'refresh credentials', 'contact support']
TICKETS = 1600
QUERIES = ['payments timeout retry', 'missing reports permissions', 'webhooks delayed logs',
           'accounts invalid credentials', 'storage unavailable connection']


def search():
    index = {}
    for ticket_id in range(TICKETS):
        product = PRODUCTS[ticket_id % len(PRODUCTS)]
        symptom = SYMPTOMS[(ticket_id // 7 + ticket_id // 53) % len(SYMPTOMS)]
        action = ACTIONS[(ticket_id // 11 + ticket_id // 29) % len(ACTIONS)]
        text = (product + ' request ' + symptom + ' customer ' + str(ticket_id % 113)
                + ' region ' + str(ticket_id % 17) + ' ' + action + ' ' + product)
        counts = {}
        for word in text.lower().split():
            counts[word] = counts.get(word, 0) + 1
        for word, count in counts.items():
            if word not in index:
                index[word] = []
            index[word].append((ticket_id, count))
    weights = {word: math.log(1 + TICKETS / len(postings)) for word, postings in index.items()}
    norms = [0.0] * TICKETS
    for word, postings in index.items():
        for ticket_id, count in postings:
            weight = count * weights[word]
            norms[ticket_id] += weight * weight
    norms = [math.sqrt(value) for value in norms]
    print('tickets: ' + str(TICKETS))
    print('terms: ' + str(len(index)))
    for query in QUERIES:
        scores = {}
        for word in query.split():
            if word in index:
                for ticket_id, count in index[word]:
                    scores[ticket_id] = scores.get(ticket_id, 0.0) + count * weights[word] ** 2
        ranked = [(int(score / norms[ticket_id] * 1000000), ticket_id)
                  for ticket_id, score in scores.items()]
        ranked.sort(key=lambda pair: (-pair[0], pair[1]))
        print(query + ': ' + ','.join(str(ticket_id) + '=' + str(score)
                                     for score, ticket_id in ranked[:5]))


search()
