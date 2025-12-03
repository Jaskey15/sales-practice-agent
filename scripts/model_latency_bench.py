import argparse
import logging
from statistics import mean
from time import perf_counter
from typing import Any, Iterable, Sequence

from agents.persona import SarahPersona
from config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DEFAULT_MODELS: Sequence[str] = (
    "gpt-4o-mini",
    "gemini-flash",
    "mixtral-instruct",
    "llama-3-8b-chat",
)


def _coerce_usage_value(usage: Any, key: str) -> int:
    """
    Safely extract token usage values regardless of object/dict shape.
    """
    if usage is None:
        return 0

    value = getattr(usage, key, None)
    if value is not None:
        return int(value)

    if isinstance(usage, dict):
        return int(usage.get(key, 0))

    return 0


def bench_models(
    models: Iterable[str],
    prompt: str,
    repeat: int,
    http_referer: str | None,
    x_title: str | None,
) -> None:
    settings = get_settings()

    for model in models:
        logger.info("Benchmarking model %s with repeat=%d", model, repeat)

        persona = SarahPersona(
            api_key=settings.openrouter_api_key,
            model=model,
            http_referer=http_referer or settings.openrouter_http_referer,
            x_title=x_title or settings.openrouter_x_title,
        )

        latencies_ms: list[float] = []
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        latest_response = ""

        for iteration in range(repeat):
            persona.reset_conversation()

            start_time = perf_counter()
            latest_response = persona.respond(prompt)
            elapsed_ms = (perf_counter() - start_time) * 1_000
            latencies_ms.append(elapsed_ms)

            usage = persona.last_usage
            prompt_tokens += _coerce_usage_value(usage, "prompt_tokens")
            completion_tokens += _coerce_usage_value(usage, "completion_tokens")
            total_tokens += _coerce_usage_value(usage, "total_tokens")

            logger.debug(
                "Model=%s iteration=%d latency=%.1fms usage=%s",
                model,
                iteration + 1,
                elapsed_ms,
                usage,
            )

        avg_latency = mean(latencies_ms)
        min_latency = min(latencies_ms)
        max_latency = max(latencies_ms)

        logger.info(
            "Model=%s avg_latency=%.1fms min=%.1fms max=%.1fms prompt_tokens=%d completion_tokens=%d total_tokens=%d",
            model,
            avg_latency,
            min_latency,
            max_latency,
            prompt_tokens,
            completion_tokens,
            total_tokens,
        )

        excerpt = latest_response.replace("\n", " ")[:120]
        print(
            f"{model:<20} avg {avg_latency:7.1f} ms  "
            f"min {min_latency:7.1f} ms  max {max_latency:7.1f} ms  "
            f"prompt {prompt_tokens:5d}  completion {completion_tokens:5d}  total {total_tokens:5d}  "
            f"sample: {excerpt!r}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare OpenRouter chat models for latency and token usage."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_MODELS),
        help="Space-separated list of model names to benchmark.",
    )
    parser.add_argument(
        "--prompt",
        default=(
            "Hi Sarah, can you summarize the value of our sales coaching product in one short paragraph?"
        ),
        help="Prompt to send to each model.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of times to call each model (use >1 to average results).",
    )
    parser.add_argument(
        "--http-referer",
        help="Override the HTTP-Referer header for OpenRouter attribution.",
    )
    parser.add_argument(
        "--x-title",
        help="Override the X-Title header for OpenRouter attribution.",
    )

    args = parser.parse_args()

    if args.repeat < 1:
        parser.error("--repeat must be >= 1")

    bench_models(
        models=args.models,
        prompt=args.prompt,
        repeat=args.repeat,
        http_referer=args.http_referer,
        x_title=args.x_title,
    )


if __name__ == "__main__":
    main()

