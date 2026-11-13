"""Chart (PNG) and results table (CSV) generation."""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.rcParams["font.family"] = "Noto Sans CJK JP"
matplotlib.rcParams["axes.unicode_minus"] = False

from src.backtest import find_designation_row


def plot_case(df: pd.DataFrame, score: pd.Series, case: dict, output_dir: str, breach_level: float = None) -> str:
    d = find_designation_row(df, case["designation_date"])

    os.makedirs(output_dir, exist_ok=True)
    fig, (ax_price, ax_score) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

    ax_price.plot(df.index, df["close"], color="tab:blue")
    ax_price.set_ylabel("종가")
    ax_price.set_title(f"{case['name']} ({case['ticker']}) — 지정일 {case['designation_date']}")
    ax_price.axvline(d, color="red", linestyle="--")

    ax_score.plot(score.index, score, color="tab:orange")
    if breach_level is not None:
        ax_score.axhline(breach_level, color="gray", linestyle=":", label="탐지 임계값(베이스라인 기준)")
        ax_score.legend(loc="upper left", fontsize=8)
    ax_score.axvline(d, color="red", linestyle="--")
    ax_score.set_ylabel("복합 이상 점수")
    ax_score.set_xlabel("거래일 인덱스")

    fig.tight_layout()
    path = os.path.join(output_dir, f"{case['ticker']}_{case['name']}.png")
    fig.savefig(path)
    plt.close(fig)
    return path


def write_results_csv(results: list, output_path: str) -> None:
    columns = [
        "name", "ticker", "designation_date", "effective_date", "status",
        "lead_time_days", "false_positive_rate", "breach_level",
    ]
    pd.DataFrame(results, columns=columns).to_csv(output_path, index=False)
