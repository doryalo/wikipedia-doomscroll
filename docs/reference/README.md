# Wikimedia retrieval reference

Developer artifacts are kept together at the repository root:

- [`wikimedia_retrieval_tutorial.py`](../../wikimedia_retrieval_tutorial.py):
  executable notebook-style examples and JSON snapshot generator.
- [`wikimedia_content/page-results.schema.json`](../../wikimedia_content/page-results.schema.json):
  shared generated-data contract.
- [`wikimedia_content/models.py`](../../wikimedia_content/models.py): strict
  Pydantic v2 representations and loaders.

The generator uses official Wikimedia Action, Core REST, Analytics, and Feed
APIs only. It must send an identifying User-Agent containing
`WIKIMEDIA_CONTACT`; never use HTML scraping. For the production backend's
async gateway, caching, retry, and test policy, see
[Wikimedia integration](../../backend/docs/wikimedia-integration.md).

Rate-limit guidance remains with the executable tutorial's rate-limit example,
where it can be kept aligned with the live API behavior.

_Reference live here (Diataxis: reference)._
