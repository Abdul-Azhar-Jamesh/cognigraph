# External data

Both data sets are third-party, MIT-licensed, and used read-only. Only the files the code reads are kept here.

## QuixBugs (`QuixBugs/`)

* Source: <https://github.com/jkoppel/QuixBugs>, commit `4257f44b0ff1181dedaedee6a447e133219fcebf` (the clone had no local changes).
* Kept: `python_programs/` (buggy), `correct_python_programs/` (reference), `json_testcases/` (31 programs with JSON tests),
  `LICENSE`, `legal_notes.txt`, `README.md`. Byte-identical to the upstream files at that commit.
* Not kept (not read by any code here; re-obtainable from the commit above): the Java programs and tests, `python_testcases/`,
  `tester.py`, the paper PDF and the CI files.
* Citation: Lin, Koppel, Chen, Solar-Lezama, QuixBugs, SPLASH Companion 2017.

## HumanEvalPack, Python split (`HumanEvalPack/`)

* Source: <https://huggingface.co/datasets/bigcode/humanevalpack>, file `python/test-00000-of-00001.parquet` (164 problems; MIT per the data set card).
* `python-test.parquet`: the file as downloaded, SHA-256 `ed5f15d789156e21222bfcd556c425a39042355c84ae1e8b058abd6a3d7f8075`.
* `humanevalpack_python.jsonl`: the same rows as JSON lines with sorted keys (what the code reads), SHA-256
  `523fb78ceec3ecec82befe30fb02492575a7fddeca256dbc916b1cb264e1de10`. Rebuild from the parquet file:

  ```powershell
  python -c "import pyarrow.parquet as pq, json; t = pq.read_table(r'data\external\HumanEvalPack\python-test.parquet').to_pylist(); open(r'data\external\HumanEvalPack\humanevalpack_python.jsonl', 'w', encoding='utf-8', newline='\n').write(''.join(json.dumps(r, sort_keys=True) + '\n' for r in t))"
  ```

  (`pyarrow` is needed only for this conversion; it is not a dependency of the project.)
* `README_dataset_card_head.txt`: the first lines of the data set card (licence line).
* Citation: Muennighoff et al., OctoPack, ICLR 2024.

## Legacy sample

`../legacy/` holds the only LLM output of the original third-party project (record only; see its README).
