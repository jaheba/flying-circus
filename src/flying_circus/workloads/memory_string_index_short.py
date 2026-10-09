# Retain distinct dynamically allocated strings through validation.
COUNT = 250000
WIDTH = 8

values = {}
for index in range(COUNT):
    values[str(index).rjust(WIDTH, '0')] = index
checksum = 0
for index in range(0, COUNT, 97):
    checksum += values[str(index).rjust(WIDTH, '0')]
assert len(values) == COUNT
print(len(values), checksum, len(next(iter(values))))
