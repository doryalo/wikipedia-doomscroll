import logging
import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from time import monotonic
from typing import Generic, TypeVar
from pydantic import BaseModel

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
PRICING_VERSION = "2026-07-21"
LONG_CONTEXT_THRESHOLD = 272_000


@dataclass(frozen=True)
class ModelPrice:
    input: Decimal
    cached_input: Decimal
    output: Decimal


MODEL_PRICES = {
    "gpt-5.6-luna": ModelPrice(Decimal("1"), Decimal("0.1"), Decimal("6")),
    "gpt-5.6-terra": ModelPrice(Decimal("2.5"), Decimal("0.25"), Decimal("15")),
}


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class ObservedResponse(Generic[T]):
    output: T
    call_id: int
    response_id: str | None
    request_id: str | None
    usage: Usage
    estimated_cost_usd: Decimal | None


def _value(value: object, name: str, default: object = None) -> object:
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _usage(response: object) -> Usage:
    raw = _value(response, "usage")
    input_tokens = int(_value(raw, "input_tokens", 0) or 0)
    output_tokens = int(_value(raw, "output_tokens", 0) or 0)
    cached = int(
        _value(_value(raw, "input_tokens_details"), "cached_tokens", 0) or 0
    )
    reasoning = int(
        _value(_value(raw, "output_tokens_details"), "reasoning_tokens", 0) or 0
    )
    total = int(_value(raw, "total_tokens", input_tokens + output_tokens) or 0)
    return Usage(input_tokens, cached, output_tokens, reasoning, total)


def estimate_cost(model: str, usage: Usage) -> Decimal | None:
    price = MODEL_PRICES.get(model)
    if price is None:
        return None
    input_multiplier = Decimal("2") if usage.input_tokens > LONG_CONTEXT_THRESHOLD else Decimal("1")
    output_multiplier = Decimal("1.5") if usage.input_tokens > LONG_CONTEXT_THRESHOLD else Decimal("1")
    uncached = max(usage.input_tokens - usage.cached_input_tokens, 0)
    microdollars = input_multiplier * (
        Decimal(uncached) * price.input
        + Decimal(usage.cached_input_tokens) * price.cached_input
    ) + output_multiplier * Decimal(usage.output_tokens) * price.output
    return (microdollars / Decimal(1_000_000)).quantize(Decimal("0.000000000001"))


class OpenAIClient:
    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        sdk_client: object | None = None,
        max_retries: int = 3,
        timeout: float = 180.0,
    ) -> None:
        self.connection = connection
        self.max_retries = max_retries
        if sdk_client is None:
            from openai import OpenAI as SDKOpenAI

            sdk_client = SDKOpenAI(max_retries=max_retries, timeout=timeout)
        self.sdk_client = sdk_client

    def parse(
        self,
        *,
        operation: str,
        model: str,
        instructions: str,
        input: str,
        output_type: type[T],
        reasoning_effort: str,
        prompt_version: str,
        article_id: str | None = None,
        enrichment_run_id: int | None = None,
    ) -> ObservedResponse[T]:
        started_at = _utc_now()
        price = MODEL_PRICES.get(model)
        cursor = self.connection.execute(
            """
            INSERT INTO llm_calls (
                article_id, enrichment_run_id, operation, prompt_version, model,
                reasoning_effort, status, max_retries, pricing_version,
                input_usd_per_million, cached_input_usd_per_million,
                output_usd_per_million, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'started', ?, ?, ?, ?, ?, ?)
            """,
            (
                article_id,
                enrichment_run_id,
                operation,
                prompt_version,
                model,
                reasoning_effort,
                self.max_retries,
                PRICING_VERSION if price else None,
                str(price.input) if price else None,
                str(price.cached_input) if price else None,
                str(price.output) if price else None,
                started_at,
            ),
        )
        call_id = cursor.lastrowid
        self.connection.commit()
        started = monotonic()
        logger.info(
            "llm.start call_id=%s operation=%s model=%s article_id=%s run_id=%s max_retries=%s",
            call_id,
            operation,
            model,
            article_id,
            enrichment_run_id,
            self.max_retries,
        )
        try:
            response = self.sdk_client.responses.parse(
                model=model,
                instructions=instructions,
                input=input,
                text_format=output_type,
                reasoning={"effort": reasoning_effort},
            )
            output = _value(response, "output_parsed")
            if output is None:
                raise ValueError("OpenAI response did not contain parsed output")
            usage = _usage(response)
            cost = estimate_cost(model, usage)
            response_id = _value(response, "id")
            request_id = _value(response, "_request_id")
            latency_ms = round((monotonic() - started) * 1000)
            self.connection.execute(
                """
                UPDATE llm_calls SET
                    status = 'succeeded', response_id = ?, request_id = ?, latency_ms = ?,
                    input_tokens = ?, cached_input_tokens = ?, output_tokens = ?,
                    reasoning_tokens = ?, total_tokens = ?, estimated_cost_usd = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    response_id,
                    request_id,
                    latency_ms,
                    usage.input_tokens,
                    usage.cached_input_tokens,
                    usage.output_tokens,
                    usage.reasoning_tokens,
                    usage.total_tokens,
                    str(cost) if cost is not None else None,
                    _utc_now(),
                    call_id,
                ),
            )
            self.connection.commit()
            if cost is None:
                logger.warning("llm.cost_unknown call_id=%s model=%s", call_id, model)
            logger.info(
                "llm.done call_id=%s request_id=%s response_id=%s latency_ms=%s tokens=%s cost_usd=%s",
                call_id,
                request_id,
                response_id,
                latency_ms,
                usage.total_tokens,
                cost,
            )
            return ObservedResponse(
                output=output,
                call_id=call_id,
                response_id=response_id,
                request_id=request_id,
                usage=usage,
                estimated_cost_usd=cost,
            )
        except Exception as error:
            latency_ms = round((monotonic() - started) * 1000)
            self.connection.execute(
                """
                UPDATE llm_calls SET
                    status = 'failed', request_id = ?, status_code = ?, latency_ms = ?,
                    error_type = ?, error_message = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    getattr(error, "request_id", None),
                    getattr(error, "status_code", None),
                    latency_ms,
                    type(error).__name__,
                    str(error),
                    _utc_now(),
                    call_id,
                ),
            )
            self.connection.commit()
            logger.exception(
                "llm.failed call_id=%s operation=%s model=%s latency_ms=%s",
                call_id,
                operation,
                model,
                latency_ms,
            )
            raise


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
