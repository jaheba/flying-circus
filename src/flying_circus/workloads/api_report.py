import json

response = '''{"tickets":[
{"id":101,"team":"payments","status":"open","priority":1,"title":"Retry failed invoices"},
{"id":102,"team":"platform","status":"closed","priority":2,"title":"Rotate credentials"},
{"id":103,"team":"payments","status":"open","priority":3,"title":"Update receipt template"},
{"id":104,"team":"platform","status":"open","priority":1,"title":"Investigate elevated latency"},
{"id":105,"team":"platform","status":"open","priority":2,"title":"Add deployment checks"}
]}'''
tickets = json.loads(response)['tickets']
open_tickets = [ticket for ticket in tickets if ticket['status'] == 'open']
open_tickets.sort(key=lambda ticket: (ticket['priority'], ticket['id']))
counts = {}
for ticket in open_tickets:
    team = ticket['team']
    counts[team] = counts.get(team, 0) + 1
print('Open tickets: ' + str(len(open_tickets)))
for team in sorted(counts):
    print(team + ': ' + str(counts[team]))
for ticket in open_tickets:
    print(str(ticket['id']) + ' ' + ticket['title'])
