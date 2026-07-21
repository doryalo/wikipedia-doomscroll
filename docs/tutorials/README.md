# Generate Wikimedia example datasets

The notebook-style [`wikimedia_retrieval_tutorial.py`](../../wikimedia_retrieval_tutorial.py)
demonstrates official Wikimedia APIs and can generate the example snapshots in
[`wikimedia_content/`](../../wikimedia_content/).

Install its only dependency, set `WIKIMEDIA_CONTACT` in the script to a
monitored email or HTTPS contact URL, then generate every dataset:

```bash
python3 -m pip install httpx
python3 wikimedia_retrieval_tutorial.py --generate-json
```

To refresh only selected examples, pass their comma-separated identifiers:

```bash
python3 wikimedia_retrieval_tutorial.py \
  --generate-json-only=random-pages,most-viewed-day,related-genghis-khan
```

Generation overwrites the selected JSON files. Each file is a live Wikimedia
snapshot, so time-sensitive and random results will change between runs. See
the [data contract](../data/README.md) for the common schema and Python models,
and the [reference](../reference/README.md) for API and contact requirements.
