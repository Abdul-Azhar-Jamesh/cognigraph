---
license: mit
pretty_name: HumanEvalPack
language_creators:
- expert-generated
multilinguality:
- multilingual
language:
- code
tags:
- code
dataset_info:
- config_name: cpp
  features:
  - name: task_id
    dtype: string
  - name: prompt
    dtype: string
  - name: declaration
    dtype: string
  - name: canonical_solution
    dtype: string
  - name: buggy_solution
    dtype: string
  - name: bug_type
    dtype: string
  - name: failure_symptoms
    dtype: string
  - name: entry_point
    dtype: string
