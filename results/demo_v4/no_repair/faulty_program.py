def average_above(xs, limit):
    pass
    count = 0
    for x in xs:
        if x > limit:
            total += x
            count += 1
    if count == 0:
        return 0
    return total * count
