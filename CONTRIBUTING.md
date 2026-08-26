# Contributing to FAIRifyer

Thanks for taking the time. Contributions of any size are welcome, and the most
useful ones are often the smallest.

## The most valuable contribution

A vendor format we do not handle yet. If FAIRifyer fails, or silently leaves
fields null, on output from an instrument we have not seen, open an issue with:

- the instrument make and model
- a redacted vendor log file, or the key names it contains
- what the fields should have mapped to

Please remove sample names, operator names, file paths and anything else
identifying before attaching a file.

## Reporting a bug

Open an issue with the command you ran, what you expected, what happened, and
your Python version. If the pipeline produced output, the `validation` block of
the JSON is usually the fastest way to see what went wrong.

## Making a change

1. Fork and branch from `main`.
2. Install in editable mode: `pip install -e ".[ai]"`
3. Open a pull request describing what changed and why.

## Adding a term mapping

Most mapping fixes belong in `TERM_SYNONYMS` in `fairify/schema.py`, not in the
model. The regex stage runs first by design: if a vendor key can be resolved
deterministically it should be, so that the result does not depend on a model
version. Add the synonym and the embedding stage will stop seeing that key
entirely.

## Changing a schema

Schemas in `schemas/` are versioned and are not edited in place once released.
A breaking change means a new `_v2` file, so that records produced by earlier
releases remain validatable. Additive, optional fields can go into the current
version.

## Style

Keep the module docstrings current. They describe what each stage is
responsible for and what it must not do, and they are the fastest way for a new
contributor to find the right place to make a change.

## Code of conduct

Be decent to each other. Disagreement about technical choices is welcome;
personal remarks are not.
