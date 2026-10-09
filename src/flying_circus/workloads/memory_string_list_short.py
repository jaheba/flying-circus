# Retain distinct dynamically allocated strings through validation.
COUNT = 500000
WIDTH = 8

values = []
for index in range(COUNT):
    values.append(str(index).rjust(WIDTH, '0'))
checksum = sum(len(value) for value in values)
assert len(values) == COUNT
assert values[12345] == str(12345).rjust(WIDTH, '0')
print(len(values), checksum, values[-1])
