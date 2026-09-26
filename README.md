# lager

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)

Household inventory: what is in the house, how much of it is left, what expires
when, and which piece of electronics is too important to sell. Part of the
[Saganta Suite](https://github.com/sami-djouhri/saganta-suite), usable on its
own. All user-facing text is German.

## What it is for

Two questions, and they are different enough to need different handling.

**Consumables** are counted and expire. The interesting endpoint is
`/api/critical`, which the suite's daily briefing calls: what is running out,
what is about to go off. Stock is consumed oldest-first, and unit conversion
happens in one place (`app/domain.py`) so that half a litre and 500 ml are the
same amount everywhere.

**Electronics** are not counted, they are judged. Each asset carries a usage
status, and the interesting one is "in active use for something that matters".
It exists to answer "can I sell this?" with something better than memory, and to
stop the answer being yes for a machine three other things depend on.

## One thing worth knowing

`SQL != 'x'` does not match NULL. On a nullable column, "everything that is not
x" quietly excludes every row where the value was never set, which in an
inventory means the rows nobody has got round to classifying yet. Those are
exactly the rows you were asking about. Every such comparison here is written as
`or_(col.is_(None), col != 'x')`.

## Tests

```bash
./run-tests.sh
```

## License

AGPL-3.0.

## About this snapshot

The recipe, not the data. Operating notes, the secrets vault and the
home-network compose overlay are not in here.

`app/services/homelab_inventory.py` seeds a few example machines for the
electronics part. It is called only on an explicit request, never at startup,
and the entries are examples: replace them with your own hardware or ignore the
endpoint.

The development history stays private; the public one starts at the first
release and grows with each one.
