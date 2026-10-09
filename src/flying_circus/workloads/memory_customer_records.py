# Keep a customer export alive, including independently created short field values.
COUNT = 100000
records = []
for index in range(COUNT):
    records.append({
        'id': str(index).rjust(8, '0'),
        'region': 'r' + str(index % 100),
        'plan': 'p' + str(index % 10),
        'status': 's' + str(index % 4),
        'tags': ['t' + str(index % 50), 't' + str(index % 17)],
    })
checksum = 0
for record in records:
    checksum += len(record['id']) + len(record['region']) + len(record['plan'])
    checksum += len(record['status']) + sum(len(tag) for tag in record['tags'])
assert len(records) == COUNT
assert records[-1]['id'] == '00099999'
print(len(records), checksum)
