raw = '''region,product,units,unit_price
 North ,Widget,12,9.50
EAST,Gadget,2,42.00
south,Widget,7,9.50
north,Gadget,3,42.00
West,Widget,,9.50
East,Widget,5,9.50
'''
rows = []
rejected = 0
for line in raw.splitlines()[1:]:
    region, product, units, price = [field.strip() for field in line.split(',')]
    if not units:
        rejected += 1
        continue
    whole, fraction = price.split('.')
    cents = int(whole) * 100 + int(fraction)
    rows.append({'region': region.lower(), 'product': product, 'cents': int(units) * cents})
totals = {}
for row in rows:
    region = row['region']
    totals[region] = totals.get(region, 0) + row['cents']
for region in sorted(totals):
    print(region + ': ' + str(totals[region]))
print('rejected: ' + str(rejected))
