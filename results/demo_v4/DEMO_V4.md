# Demonstration of the interventional model (generated)

Three cases chosen by fixed rules from the development benchmark. Parameters for each case are
estimated without the program it comes from. Columns give P(statement is faulty) under three models.

## Two faults: the mechanism the model was built for

Selection rule: first two-fault program, in identifier order, where version 3 fused does not have both faults in its top 3 and the interventional model does

Case `average_above:3:CRP:0+5:ROR-flip:0`. 9 of 9 tests fail.

```
  1  def average_above(xs, limit):
  2      total = 0
  3      count = 1
  4      for x in xs:
  5          if x < limit:
  6              total += x
  7              count += 1
  8      if count == 0:
  9          return 0
 10      return total / count
```

| Line | Statement | Failing tests that run it | Variants | Best variant fixes | Version 3 reads this as | Spectrum only | Version 3 fused | Interventional |
|---|---|---|---|---|---|---|---|---|
| 2 | `total = 0` | 9 | 3 | 1 of 9 | partial | 0.271 | 0.059 | **0.184** |
| 3 | `count = 1` | 9 | 3 | 2 of 9 | partial | 0.271 | 0.059 | **0.221** |
| 4 | `for x in xs:` | 9 | 0 | 0 of 9 | no variant | 0.271 | 0.798 | **0.161** |
| 5 | `if x < limit:` | 8 | 3 | 0 of 8 | no effect | 0.149 | 0.159 | **0.678** |
| 6 | `total += x` | 2 | 2 | 0 of 2 | no effect | 0.117 | 0.119 | **0.119** |
| 7 | `count += 1` | 2 | 4 | 0 of 2 | no effect | 0.117 | 0.119 | **0.119** |
| 8 | `if count == 0:` | 9 | 4 | 3 of 9 | partial | 0.271 | 0.059 | **0.193** |
| 9 | `return 0` | 0 | 2 | 0 of 0 | no effect | 0.111 | 0.111 | **0.111** |
| 10 | `return total / count` | 9 | 1 | 2 of 9 | partial | 0.271 | 0.059 | **0.543** |

Interventional model: probability of 1 fault: 0.04, 2 faults: 0.69, 3 faults: 0.26. Most probable set of faulty lines: {5, 10}.

Ground truth (evaluation only): faulty lines 3, 5. A restoring variant exists for 0 of 2.

| Model | Mid-rank of each faulty line | Average precision |
|---|---|---|
| Spectrum only | 3, 6 | 0.333 |
| Version 3 fused | 7.5, 2 | 0.383 |
| Interventional | 3, 1 | 0.833 |

## One fault: where allowing several faults costs accuracy

Selection rule: first single-fault program where version 3 fused ranks the fault first and the interventional model does not

Case `average_above:3:CRP:0`. 9 of 9 tests fail.

```
  1  def average_above(xs, limit):
  2      total = 0
  3      count = 1
  4      for x in xs:
  5          if x > limit:
  6              total += x
  7              count += 1
  8      if count == 0:
  9          return 0
 10      return total / count
```

| Line | Statement | Failing tests that run it | Variants | Best variant fixes | Version 3 reads this as | Spectrum only | Version 3 fused | Interventional |
|---|---|---|---|---|---|---|---|---|
| 2 | `total = 0` | 9 | 3 | 1 of 9 | partial | 0.270 | 0.009 | **0.001** |
| 3 | `count = 1` | 9 | 3 | 9 of 9 | all tests pass | 0.270 | 0.996 | **0.013** |
| 4 | `for x in xs:` | 9 | 0 | 0 of 9 | no variant | 0.270 | 0.130 | **0.002** |
| 5 | `if x > limit:` | 8 | 3 | 0 of 8 | no effect | 0.145 | 0.150 | **0.002** |
| 6 | `total += x` | 6 | 2 | 0 of 6 | no effect | 0.132 | 0.135 | **0.290** |
| 7 | `count += 1` | 6 | 4 | 1 of 6 | partial | 0.132 | 0.135 | **0.742** |
| 8 | `if count == 0:` | 9 | 4 | 3 of 9 | partial | 0.270 | 0.009 | **0.423** |
| 9 | `return 0` | 0 | 2 | 0 of 0 | no effect | 0.111 | 0.111 | **0.111** |
| 10 | `return total / count` | 9 | 1 | 3 of 9 | partial | 0.270 | 0.009 | **0.563** |

Interventional model: probability of 1 fault: 0.01, 2 faults: 0.94, 3 faults: 0.05. Most probable set of faulty lines: {7, 10}.

Ground truth (evaluation only): faulty line 3. A restoring variant exists for 1 of 1.

| Model | Mid-rank of each faulty line | Average precision |
|---|---|---|
| Spectrum only | 3 | 0.333 |
| Version 3 fused | 1 | 1.000 |
| Interventional | 6 | 0.167 |

## Two faults, no variant of either faulty statement fixes a failing test: the evidence is missing

Selection rule: first two-fault program in which no variant of either faulty statement makes any failing test pass

Case `average_above:10:AOR:0+2:SDL:0`. 6 of 9 tests fail.

```
  1  def average_above(xs, limit):
  2      pass
  3      count = 0
  4      for x in xs:
  5          if x > limit:
  6              total += x
  7              count += 1
  8      if count == 0:
  9          return 0
 10      return total * count
```

| Line | Statement | Failing tests that run it | Variants | Best variant fixes | Version 3 reads this as | Spectrum only | Version 3 fused | Interventional |
|---|---|---|---|---|---|---|---|---|
| 2 | `pass` | 6 | 0 | 0 of 6 | no variant | 0.005 | 0.072 | **0.058** |
| 3 | `count = 0` | 6 | 3 | 0 of 6 | no effect | 0.005 | 0.002 | **0.003** |
| 4 | `for x in xs:` | 6 | 0 | 0 of 6 | no variant | 0.005 | 0.072 | **0.058** |
| 5 | `if x > limit:` | 6 | 3 | 0 of 6 | no effect | 0.013 | 0.006 | **0.008** |
| 6 | `total += x` | 6 | 2 | 0 of 6 | no effect | 0.986 | 0.858 | **0.899** |
| 7 | `count += 1` | 0 | 4 | 0 of 0 | no effect | 0.111 | 0.111 | **0.111** |
| 8 | `if count == 0:` | 0 | 4 | 0 of 0 | no effect | 0.001 | 0.002 | **0.000** |
| 9 | `return 0` | 0 | 2 | 0 of 0 | no effect | 0.001 | 0.002 | **0.000** |
| 10 | `return total * count` | 0 | 1 | 0 of 0 | no effect | 0.111 | 0.111 | **0.111** |

Interventional model: probability of 1 fault: 0.98, 2 faults: 0.02, 3 faults: 0.00. Most probable set of faulty lines: {6}.

Ground truth (evaluation only): faulty lines 2, 10. A restoring variant exists for 0 of 2.

| Model | Mid-rank of each faulty line | Average precision |
|---|---|---|
| Spectrum only | 6, 2.5 | 0.367 |
| Version 3 fused | 4.5, 2.5 | 0.422 |
| Interventional | 4.5, 2.5 | 0.422 |
