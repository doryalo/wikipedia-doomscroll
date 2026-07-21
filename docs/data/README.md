# Data and schemas

`wikimedia_content/` holds generated page-result snapshots. Every example file
uses the shared [`page-results.schema.json`](../../wikimedia_content/page-results.schema.json)
contract and contains at most 10 ranked pages.

Each page has:

- discovery data from the originating endpoint;
- stable page/revision identity and canonical URL;
- a text-only page card (description, Wikidata ID, size, last-touched, and
  disambiguation status); and
- complete plain-text article content.

The contract deliberately contains no image fields. `expansion.shortfall` is
`false` only when an example has exactly 10 results; otherwise it records why a
source could not naturally supply that many pages.

Use the strict Pydantic v2 companion
[`models.py`](../../wikimedia_content/models.py) to load and validate the
snapshots:

```python
from wikimedia_content.models import load_all_datasets, load_dataset

random_pages = load_dataset("wikimedia_content/random-pages.json")
all_datasets = load_all_datasets()
```

The models reject fields outside the contract and validate counts, sequential
ranks, and duplicate page identities. Regenerate snapshots with the
[dataset tutorial](../tutorials/README.md).
