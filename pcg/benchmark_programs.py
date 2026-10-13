"""The benchmark: small reference programs, each with a hand-written test suite.

Each entry gives a correct reference implementation and a list of test inputs.
The expected output of every test is whatever the reference implementation
returns (or raises) for that input, so the reference is the oracle. The unit
tests in ``tests/test_benchmark.py`` additionally pin a few literal expected
values per program so that a wrong reference cannot go unnoticed.

Inputs are restricted to JSON values (numbers, strings, booleans, lists, null)
because they are sent to the runner process as JSON.

``has_close_elements`` is problem 0 of the HumanEval benchmark (Chen et al.,
2021) and was the single example of the original project. The other programs
were written for this project; see LIMITATIONS.md for what that implies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkProgram:
    """A reference implementation with its test inputs."""

    name: str
    source: str
    tests: tuple[tuple, ...]


def _p(name: str, source: str, tests: list[list]) -> BenchmarkProgram:
    return BenchmarkProgram(name, source.strip() + "\n", tuple(tuple(t) for t in tests))


PROGRAMS: tuple[BenchmarkProgram, ...] = (
    _p("has_close_elements", """
def has_close_elements(numbers, threshold):
    for i in range(len(numbers)):
        for j in range(i + 1, len(numbers)):
            if abs(numbers[i] - numbers[j]) < threshold:
                return True
    return False
""", [
        [[1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3], [[1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05],
        [[1.0, 2.0, 5.9, 4.0, 5.0], 0.95], [[1.0, 2.0, 5.9, 4.0, 5.0], 0.8],
        [[1.0, 2.0, 3.0, 4.0, 5.0, 2.0], 0.1], [[1.1, 2.2, 3.1, 4.1, 5.1], 1.0],
        [[1.1, 2.2, 3.1, 4.1, 5.1], 0.5], [[], 1.0], [[1.0], 1.0], [[1.0, 1.0], 0.5],
        [[1.0, 3.0], 2.0], [[5.0, 1.0], 1.0],
    ]),
    _p("max_of_list", """
def max_of_list(numbers):
    if len(numbers) == 0:
        return None
    result = numbers[0]
    for n in numbers[1:]:
        if n > result:
            result = n
    return result
""", [[[]], [[3]], [[1, 2, 3]], [[3, 2, 1]], [[2, 5, 1]], [[-1, -5]], [[4, 4]], [[0, -1, 7, 7, 2]], [[-3]]]),
    _p("count_positive", """
def count_positive(xs):
    count = 0
    for x in xs:
        if x > 0:
            count += 1
    return count
""", [[[]], [[1]], [[0]], [[-1]], [[1, 2, 3]], [[-1, 0, 1]], [[0, 0]], [[5, -5, 5]], [[-2, -3]]]),
    _p("sum_even", """
def sum_even(xs):
    total = 0
    for x in xs:
        if x % 2 == 0:
            total += x
    return total
""", [[[]], [[2]], [[1]], [[1, 3, 5]], [[2, 4, 6]], [[1, 2, 3, 4]], [[0]], [[-2, 3, 8]], [[7, 10]]]),
    _p("clamp", """
def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x
""", [[5, 0, 10], [-1, 0, 10], [11, 0, 10], [0, 0, 10], [10, 0, 10], [3, 3, 3], [-5, -3, -1], [2, -3, -1], [-2, -3, -1]]),
    _p("sign", """
def sign(x):
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0
""", [[5], [-5], [0], [1], [-1], [100], [-100]]),
    _p("is_sorted", """
def is_sorted(xs):
    for i in range(len(xs) - 1):
        if xs[i] > xs[i + 1]:
            return False
    return True
""", [[[]], [[1]], [[1, 2]], [[2, 1]], [[1, 1]], [[1, 2, 3]], [[1, 3, 2]], [[3, 2, 1]], [[1, 2, 2, 5]], [[2, 1, 3]]]),
    _p("binary_search", """
def binary_search(xs, target):
    lo = 0
    hi = len(xs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if xs[mid] == target:
            return mid
        if xs[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
""", [
        [[], 1], [[1], 1], [[1], 2], [[1], 0], [[1, 3, 5], 1], [[1, 3, 5], 3], [[1, 3, 5], 5],
        [[1, 3, 5], 4], [[1, 3, 5, 7], 7], [[1, 3, 5, 7], 0], [[1, 3, 5, 7, 9, 11], 9], [[2, 4], 4],
    ]),
    _p("gcd", """
def gcd(a, b):
    while b != 0:
        r = a % b
        a = b
        b = r
    return a
""", [[12, 18], [18, 12], [7, 13], [5, 0], [0, 5], [9, 9], [1, 10], [100, 75], [17, 51]]),
    _p("is_prime", """
def is_prime(n):
    if n < 2:
        return False
    d = 2
    while d * d <= n:
        if n % d == 0:
            return False
        d += 1
    return True
""", [[0], [1], [2], [3], [4], [9], [11], [15], [25], [29], [49], [-7]]),
    _p("factorial", """
def factorial(n):
    if n < 0:
        raise ValueError('negative')
    result = 1
    i = 2
    while i <= n:
        result *= i
        i += 1
    return result
""", [[0], [1], [2], [3], [5], [6], [-1], [-4]]),
    _p("fib", """
def fib(n):
    a = 0
    b = 1
    for _ in range(n):
        c = a + b
        a = b
        b = c
    return a
""", [[0], [1], [2], [3], [4], [5], [8], [10]]),
    _p("classify_triangle", """
def classify_triangle(a, b, c):
    if a <= 0 or b <= 0 or c <= 0:
        return 'invalid'
    if a + b <= c or a + c <= b or b + c <= a:
        return 'invalid'
    if a == b and b == c:
        return 'equilateral'
    if a == b or b == c or a == c:
        return 'isosceles'
    return 'scalene'
""", [
        [3, 3, 3], [3, 3, 4], [3, 4, 3], [4, 3, 3], [3, 4, 5], [0, 4, 5], [3, -1, 5], [3, 4, 0],
        [1, 2, 3], [1, 3, 2], [3, 1, 2], [1, 1, 5], [5, 5, 9], [2, 3, 4],
    ]),
    _p("grade", """
def grade(score):
    if score < 0 or score > 100:
        return 'invalid'
    if score >= 90:
        return 'A'
    if score >= 75:
        return 'B'
    if score >= 60:
        return 'C'
    return 'F'
""", [[-1], [0], [59], [60], [61], [74], [75], [89], [90], [100], [101], [45]]),
    _p("is_leap_year", """
def is_leap_year(year):
    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    if year % 4 == 0:
        return True
    return False
""", [[2000], [1900], [2024], [2023], [2100], [1600], [2004], [2001], [4], [100]]),
    _p("first_negative_index", """
def first_negative_index(xs):
    index = 0
    for x in xs:
        if x < 0:
            return index
        index += 1
    return -1
""", [[[]], [[1]], [[-1]], [[1, -1]], [[1, 2, -3, -4]], [[0, 0]], [[-5, 1]], [[3, 0, -1]], [[2, 4, 6, 8]]]),
    _p("second_largest", """
def second_largest(xs):
    if len(xs) < 2:
        return None
    first = max(xs[0], xs[1])
    second = min(xs[0], xs[1])
    for x in xs[2:]:
        if x > first:
            second = first
            first = x
        elif x > second:
            second = x
    return second
""", [
        [[]], [[1]], [[1, 2]], [[2, 1]], [[1, 2, 3]], [[3, 2, 1]], [[1, 3, 2]], [[5, 5]],
        [[4, 1, 3]], [[2, 9, 4, 7]], [[1, 2, 2]], [[-1, -2, -3]],
    ]),
    _p("bubble_sort", """
def bubble_sort(xs):
    items = list(xs)
    n = len(items)
    for i in range(n):
        for j in range(n - i - 1):
            if items[j] > items[j + 1]:
                tmp = items[j]
                items[j] = items[j + 1]
                items[j + 1] = tmp
    return items
""", [[[]], [[1]], [[1, 2]], [[2, 1]], [[3, 1, 2]], [[1, 2, 3]], [[3, 2, 1]], [[2, 2, 1]], [[5, 1, 4, 2, 3]], [[1, 1]]]),
    _p("count_vowels", """
def count_vowels(text):
    count = 0
    for ch in text:
        if ch in 'aeiou':
            count += 1
    return count
""", [[""], ["a"], ["b"], ["hello"], ["xyz"], ["aeiou"], ["banana"], ["sky"], ["queue"]]),
    _p("is_palindrome", """
def is_palindrome(text):
    left = 0
    right = len(text) - 1
    while left < right:
        if text[left] != text[right]:
            return False
        left += 1
        right -= 1
    return True
""", [[""], ["a"], ["aa"], ["ab"], ["aba"], ["abc"], ["abba"], ["abca"], ["racecar"], ["abcda"]]),
    _p("running_max", """
def running_max(xs):
    result = []
    best = None
    for x in xs:
        if best is None or x > best:
            best = x
        result.append(best)
    return result
""", [[[]], [[1]], [[1, 2]], [[2, 1]], [[1, 3, 2, 5]], [[5, 4, 3]], [[2, 2]], [[-1, -3, 0]], [[0, 0, 1]]]),
    _p("merge_sorted", """
def merge_sorted(a, b):
    result = []
    i = 0
    j = 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    while i < len(a):
        result.append(a[i])
        i += 1
    while j < len(b):
        result.append(b[j])
        j += 1
    return result
""", [
        [[], []], [[1], []], [[], [1]], [[1], [2]], [[2], [1]], [[1, 3], [2, 4]], [[1, 2], [3, 4]],
        [[3, 4], [1, 2]], [[1, 1], [1]], [[1, 5, 9], [2]], [[2], [1, 5, 9]], [[1, 2, 3], [1, 2, 3]],
    ]),
    _p("fizzbuzz", """
def fizzbuzz(n):
    if n % 15 == 0:
        return 'FizzBuzz'
    if n % 3 == 0:
        return 'Fizz'
    if n % 5 == 0:
        return 'Buzz'
    return str(n)
""", [[1], [2], [3], [5], [6], [10], [15], [30], [7], [9], [20], [45]]),
    _p("median", """
def median(xs):
    items = sorted(xs)
    n = len(items)
    if n == 0:
        return None
    mid = n // 2
    if n % 2 == 1:
        return items[mid]
    return (items[mid - 1] + items[mid]) / 2
""", [[[]], [[1]], [[1, 2]], [[2, 1]], [[3, 1, 2]], [[1, 2, 3, 4]], [[4, 1, 3, 2]], [[5, 5, 5]], [[1, 9]], [[7, 3, 5, 1, 9]]]),
    _p("ranges_overlap", """
def ranges_overlap(a_start, a_end, b_start, b_end):
    if a_end < b_start:
        return False
    if b_end < a_start:
        return False
    return True
""", [[1, 3, 4, 6], [4, 6, 1, 3], [1, 4, 4, 6], [4, 6, 1, 4], [1, 5, 2, 3], [2, 3, 1, 5], [1, 2, 1, 2], [0, 0, 1, 1], [1, 1, 0, 0], [0, 10, 5, 15]]),
    _p("collatz_steps", """
def collatz_steps(n):
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps
""", [[1], [2], [3], [4], [5], [6], [7], [8], [16], [27]]),
    _p("remove_duplicates", """
def remove_duplicates(xs):
    seen = []
    result = []
    for x in xs:
        if x not in seen:
            seen.append(x)
            result.append(x)
    return result
""", [[[]], [[1]], [[1, 1]], [[1, 2]], [[1, 2, 1]], [[2, 2, 2]], [[3, 1, 3, 2, 1]], [[1, 2, 3]], [["a", "b", "a"]]]),
    _p("days_in_month", """
def days_in_month(month, leap):
    if month < 1 or month > 12:
        return 0
    if month == 2:
        if leap:
            return 29
        return 28
    if month in [4, 6, 9, 11]:
        return 30
    return 31
""", [
        [0, False], [13, False], [1, False], [2, False], [2, True], [3, False], [4, False], [5, True],
        [6, False], [7, False], [8, False], [9, True], [10, False], [11, False], [12, False], [-1, True],
    ]),
    _p("index_of_min", """
def index_of_min(xs):
    if not xs:
        return -1
    best = 0
    for i in range(1, len(xs)):
        if xs[i] < xs[best]:
            best = i
    return best
""", [[[]], [[5]], [[1, 2]], [[2, 1]], [[3, 1, 2]], [[1, 1]], [[4, 3, 2, 1]], [[2, 9, 2]], [[7, 8, 0, 5]]]),
    _p("average_above", """
def average_above(xs, limit):
    total = 0
    count = 0
    for x in xs:
        if x > limit:
            total += x
            count += 1
    if count == 0:
        return 0
    return total / count
""", [[[], 0], [[1], 0], [[1], 1], [[1, 2, 3], 1], [[1, 2, 3], 5], [[4, 6], 0], [[-1, -2], -3], [[10, 0, 20], 5], [[2, 2], 1]]),
    _p("count_in_range", """
def count_in_range(xs, lo, hi):
    count = 0
    for x in xs:
        if lo <= x and x <= hi:
            count += 1
    return count
""", [[[], 0, 1], [[1], 1, 1], [[0], 1, 2], [[3], 1, 2], [[1, 2, 3], 1, 3], [[1, 2, 3], 2, 2], [[5, 6], 1, 4], [[1, 5, 9], 5, 9], [[0, 10], 1, 9]]),
    _p("int_sqrt", """
def int_sqrt(n):
    if n < 0:
        raise ValueError('negative')
    r = 0
    while (r + 1) * (r + 1) <= n:
        r += 1
    return r
""", [[0], [1], [2], [3], [4], [8], [9], [15], [16], [-1], [-9]]),
    _p("absolute_difference", """
def absolute_difference(a, b):
    if a >= b:
        diff = a - b
    else:
        diff = b - a
    return diff
""", [[5, 3], [3, 5], [4, 4], [0, 7], [7, 0], [-2, 2], [2, -2], [-3, -8]]),
    _p("shipping_cost", """
def shipping_cost(weight, express):
    if weight <= 0:
        return 0
    cost = 5
    if weight > 10:
        cost += 2 * (weight - 10)
    if express:
        cost *= 2
    return cost
""", [[0, False], [-1, True], [1, False], [1, True], [10, False], [11, False], [11, True], [20, False], [20, True], [5, True]]),
)

BY_NAME = {program.name: program for program in PROGRAMS}
