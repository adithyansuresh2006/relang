# picoc

C interpreter — executes a subset of the C language.

| Field | Value |
|-------|-------|
| **Type** | Medium |
| **Score** | 400 |
| **Reference** | C |

## Prerequisites

- GCC
- GNU Make
- libreadline-dev

## Prerequisites

- Python 3

## Build

No build required — it's a Python 3 script.

## Run

```bash
python3 picoc/target/picoc.py
```

## Validate (local)

```bash
cd relang && python3 validate.py "../target/picoc.py"
```

## Submit

```bash
source setup.sh
relang "python3 picoc/target/picoc.py"
```

> ⚠️ **Do NOT submit the source reference implementation.**  
> Only implement and submit your code from `target/`.  
> Submitting `source/` may result in **disqualification**.

