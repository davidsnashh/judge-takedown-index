"""Render the Judge Takedown Index as an official scorecard image."""

import json
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle

RESULTS_DIR = Path("results")
FONT_DIR = Path("fonts")
FONT_BASE = "https://raw.githubusercontent.com/google/fonts/main/"
FONTS = {
    "black": "ofl/barlowcondensed/BarlowCondensed-Black.ttf",
    "cond": "ofl/barlowcondensed/BarlowCondensed-SemiBold.ttf",
    "reg": "ofl/barlow/Barlow-Regular.ttf",
    "med": "ofl/barlow/Barlow-Medium.ttf",
    "semi": "ofl/barlow/Barlow-SemiBold.ttf",
    "marker": "apache/permanentmarker/PermanentMarker-Regular.ttf",
}
PAPER, INK, RULE, MUTED = "#f9f8f4", "#141410", "#cfd1d8", "#6f727b"
RED, BLUE, GRAY_LINE, GRAY_DOT = "#c8102e", "#1f47b5", "#c3c5cd", "#7c7f88"
X_MIN, X_MAX = -5, 7


def load_fonts():
    FONT_DIR.mkdir(exist_ok=True)
    props = {}
    for key, path in FONTS.items():
        local = FONT_DIR / Path(path).name
        if not local.exists():
            resp = requests.get(FONT_BASE + path, timeout=60)
            resp.raise_for_status()
            local.write_bytes(resp.content)
        font_manager.fontManager.addfont(str(local))
        props[key] = FontProperties(fname=str(local))
    return props


def minus(value, digits=2):
    return f"{value:.{digits}f}".replace("-", "\u2212")


def main():
    fp = load_fonts()
    table = pd.read_csv(RESULTS_DIR / "judge_takedown_index.csv")
    table = table.sort_values("strikes_per_takedown", ascending=False).reset_index(drop=True)
    summary = json.loads((RESULTS_DIR / "summary.json").read_text())
    league = summary["pooled_rate"]
    above = table[table["above_league"]]["judge"].tolist()
    below = table[table["below_league"]]["judge"].tolist()

    fig = plt.figure(figsize=(8, 10), dpi=200)
    fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 125)
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 100, 125, fc=PAPER, ec="none"))

    def text(x, y, s, size, font, color=INK, ha="left", va="top", **kw):
        return ax.text(x, y, s, fontsize=size, fontproperties=fp[font], color=color, ha=ha, va=va, **kw)

    def hline(y, x0=6, x1=94, color=RULE, lw=0.7, **kw):
        ax.plot([x0, x1], [y, y], color=color, lw=lw, solid_capstyle="butt", **kw)

    def field(y, label, value):
        text(6, y, label, 9.5, "med", MUTED)
        text(22, y - 0.25, value, 10.5, "reg", INK)
        hline(y - 2.55, x0=22, lw=0.6)

    # header
    text(6, 120.5, "12-6 Combat Research Lab", 10.5, "cond", RED)
    text(94, 120.5, "Form JTI-001", 9, "med", MUTED, ha="right")
    text(5.6, 118.6, "OFFICIAL SCORECARD", 38, "black", INK)
    text(6, 111.9, "Judge Takedown Index", 19, "cond", INK)
    hline(106.6, lw=1.4, color=INK)
    hline(105.8, lw=0.6, color=INK)

    # form fields
    field(103.7, "Bout", "The judges  vs.  the takedown")
    field(100.7, "Event", f"Every UFC decision, {summary['first_event']} to {summary['last_event']}")
    field(97.7, "Cards scored",
          f"{summary['cards']:,} judge scorecards; {summary['judges']} judges with {summary['min_cards']} or more cards")
    text(6, 94.6, "Question", 9.5, "med", MUTED)
    text(22, 94.35, "How many significant strikes is one takedown worth on each", 10.5, "reg", INK)
    text(22, 92.15, "judge's card, beyond the control time it produces?", 10.5, "reg", INK)
    hline(89.9, x0=22, lw=0.6)

    # table geometry
    x_left, x_right = 33, 79
    top = 83.2
    row_h = min(4.2, 54.8 / len(table))
    name_size = 13 if row_h >= 4 else 11

    def xr(v):
        return x_left + (v - X_MIN) * (x_right - x_left) / (X_MAX - X_MIN)

    def yrow(i):
        return top - i * row_h

    bottom = yrow(len(table) - 1) - row_h / 2

    text(6, 87.4, "Judge", 9.5, "med", MUTED)
    text(x_left, 87.4, "Takedown credit, in significant strikes", 9.5, "med", MUTED)
    text(86, 87.4, "Score", 9.5, "med", MUTED, ha="center")
    text(95, 87.4, "Cards", 9.5, "med", MUTED, ha="center")
    hline(yrow(0) + row_h / 2, lw=0.9, color=INK)
    ax.plot([xr(league)] * 2, [bottom - 1.6, yrow(0) + row_h / 2],
            color=INK, lw=0.9, ls=(0, (3, 2.2)), zorder=1)

    for i, r in table.iterrows():
        y = yrow(i)
        name = r["judge"]
        line_c, dot_c, score_c = GRAY_LINE, GRAY_DOT, INK
        if name in above:
            line_c = dot_c = score_c = RED
            ax.add_patch(Rectangle((4, y - row_h / 2), 94, row_h, fc=RED, alpha=0.06, ec="none", zorder=0))
        if name in below:
            line_c = dot_c = score_c = BLUE
            ax.add_patch(Rectangle((4, y - row_h / 2), 94, row_h, fc=BLUE, alpha=0.05, ec="none", zorder=0))

        hline(y - row_h / 2, x0=4, x1=98, lw=0.5)
        text(6, y, name, name_size, "semi", INK, va="center")

        low, high = max(r["ci_low"], X_MIN), min(r["ci_high"], X_MAX)
        ax.plot([xr(low), xr(high)], [y, y], color=line_c, lw=2.4, solid_capstyle="round", zorder=2)
        if r["ci_low"] < X_MIN:
            text(x_left - 0.3, y - 1.3, f"\u2039 {minus(r['ci_low'], 1)}", 6.5, "reg", MUTED, va="center")
        ax.plot(xr(r["strikes_per_takedown"]), y, "o", ms=9, mfc=dot_c, mec=PAPER, mew=1.6, zorder=3)
        text(86, y + 0.25, minus(r["strikes_per_takedown"]), 15.5, "marker", score_c, ha="center", va="center")
        text(95, y, f"{int(r['cards'])}", 10.5, "reg", INK, ha="center", va="center", alpha=0.85)

        if name in above:
            text(46, y + 0.1, "OUTLIER", 17, "black", RED, ha="center", va="center", rotation=-6, alpha=0.92,
                 bbox=dict(boxstyle="square,pad=0.28", fc="none", ec=RED, lw=2.1, alpha=0.92), zorder=5)
        if name in below:
            first = "negative coefficient," if r["strikes_per_takedown"] < 0 else "below the league,"
            text(60.2, y + 1.05, first, 8.8, "reg", BLUE, va="center")
            text(60.2, y - 1.05, "interval tops out below average", 8.8, "reg", BLUE, va="center")

    hline(bottom, x0=4, x1=98, lw=0.9, color=INK)

    for v in range(-4, 7, 2):
        ax.plot([xr(v)] * 2, [bottom, bottom - 0.7], color=MUTED, lw=0.7)
        text(xr(v), bottom - 1.0, minus(v, 0), 8.5, "reg", MUTED, ha="center")
    text(xr(league), bottom - 3.4, f"league average, {league:.2f}", 8.8, "semi", INK, ha="center")
    text(xr(X_MIN), bottom - 5.9, "less credit for a takedown", 8.5, "reg", MUTED)
    text(xr(X_MAX), bottom - 5.9, "more credit for a takedown", 8.5, "reg", MUTED, ha="right")

    # footer
    fy = bottom - 8.8
    hline(fy, lw=1.2, color=INK)
    hline(fy - 0.7, lw=0.5, color=INK)

    if above:
        row = table[table["judge"] == above[0]].iloc[0]
        note1 = f"{above[0]} credits a takedown at {row['vs_league']:.1f} times the league rate, and the whole interval sits above it."
    else:
        note1 = "No judge's interval sits entirely above the league average."
    if below:
        note2 = f"{below[0]} is the mirror image. All other judges: interval includes the average, statistically ordinary."
    else:
        note2 = "All other judges: interval includes the average, statistically ordinary."
    text(6, fy - 2.3, "Notes", 9.5, "med", MUTED)
    text(22, fy - 2.5, note1, 9.5, "reg", INK)
    text(22, fy - 4.6, note2, 9.5, "reg", INK)

    text(6, fy - 7.6, "Method", 9.5, "med", MUTED)
    text(22, fy - 7.8, "Per-judge logistic regression of card outcome on differences in significant strikes, takedowns,", 9.5, "reg", INK)
    text(22, fy - 9.9, "control time and knockdowns. 95% intervals bootstrapped. Fight-level totals, and judges score", 9.5, "reg", INK)
    text(22, fy - 12.0, "rounds, so read as an approximation. Decisions only. Data: ufcstats.com via Greco1899's open scrape.", 9.5, "reg", INK)

    today = date.today()
    text(6, fy - 15.6, "Signed", 9.5, "med", MUTED)
    text(22, fy - 14.6, "12-6", 17, "marker", BLUE)
    text(40, fy - 15.3, f"{today:%B} {today.day}, {today.year}", 10, "reg", INK)
    hline(fy - 18.4, x0=22, x1=62, lw=0.6)
    text(94, fy - 15.9, "12-6 Combat Research Lab", 10.5, "cond", RED, ha="right")

    out = RESULTS_DIR / "judge_takedown_index_scorecard.png"
    plt.savefig(out, facecolor=PAPER, dpi=200)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
