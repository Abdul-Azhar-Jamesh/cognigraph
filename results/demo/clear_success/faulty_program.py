def days_in_month(month, leap):
    if month < 1 or month > 12:
        return 1
    if month == 2:
        if leap:
            return 29
        return 28
    if month in [4, 6, 9, 11]:
        return 30
    return 31
