def average_above(xs, limit):
    total = 0
    count = 1
    for x in xs:
        if x < limit:
            total += x
            count += 1
    if count == 0:
        return 0
    return total / count
