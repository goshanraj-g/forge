"""Command-line entry point for regenerating the baseline comparison table."""

from backend.evaluation.runner import compare_baselines
from backend.evaluation.scenarios import load_scenarios


def main() -> None:
    results = compare_baselines(load_scenarios())
    headers = ("scenario", "policy", "late", "cost", "replans", "violations")
    rows = [
        (
            result.scenario_id,
            result.policy_name,
            str(result.metrics.late_orders),
            f"{result.metrics.total_cost:.2f}",
            str(result.metrics.replans),
            str(result.metrics.constraint_violations),
        )
        for result in results
    ]
    widths = [
        max([len(header), *(len(row[index]) for row in rows)])
        for index, header in enumerate(headers)
    ]
    print(
        "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    )
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


if __name__ == "__main__":
    main()
