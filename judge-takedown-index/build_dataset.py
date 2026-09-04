"""Build the per-judge scorecard dataset from public ufcstats data."""

import re
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://raw.githubusercontent.com/Greco1899/scrape_ufc_stats/main/"
FILES = ["ufc_fight_results.csv", "ufc_fight_stats.csv", "ufc_event_details.csv"]
DATA_DIR = Path("data")
RESULTS_DIR = Path("results")
ERA_START = "2017-01-01"

# a judge name followed by two scores, e.g. "Derek Cleary 28 - 29."
CARD_RE = re.compile(r"([A-Za-z\u00C0-\u024F .'\-]+?)\s*(\d{1,3})\s*-\s*(\d{1,3})\.?")


def download():
    DATA_DIR.mkdir(exist_ok=True)
    for name in FILES:
        path = DATA_DIR / name
        if path.exists():
            continue
        print(f"downloading {name}")
        resp = requests.get(BASE_URL + name, timeout=120)
        resp.raise_for_status()
        path.write_bytes(resp.content)


def load():
    results = pd.read_csv(DATA_DIR / "ufc_fight_results.csv")
    stats = pd.read_csv(DATA_DIR / "ufc_fight_stats.csv")
    events = pd.read_csv(DATA_DIR / "ufc_event_details.csv")
    for df in (results, stats, events):
        for col in ("EVENT", "BOUT"):
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
    events["DATE"] = pd.to_datetime(events["DATE"], errors="coerce")
    return results, stats, events


def parse_cards(results):
    """One row per judge per decision, scores oriented to bout order."""
    decisions = results[results["METHOD"].astype(str).str.contains("Decision", na=False)]
    rows = []
    for _, r in decisions.iterrows():
        if r["OUTCOME"] not in ("W/L", "L/W"):
            continue
        fighters = [f.strip() for f in str(r["BOUT"]).split(" vs. ")]
        if len(fighters) != 2:
            continue
        for judge, a, b in CARD_RE.findall(str(r["DETAILS"])):
            judge = judge.strip(" .")
            a, b = int(a), int(b)
            if len(judge) < 5 or a > 60 or b > 60:
                continue
            # ufcstats writes the loser's score first on every card
            s1, s2 = (b, a) if r["OUTCOME"] == "W/L" else (a, b)
            rows.append({
                "EVENT": r["EVENT"], "BOUT": r["BOUT"], "OUTCOME": r["OUTCOME"],
                "f1": fighters[0], "f2": fighters[1],
                "judge": judge, "s1": s1, "s2": s2,
            })
    cards = pd.DataFrame(rows)
    cards["judge"] = cards["judge"].replace({"Sal D'amato": "Sal D'Amato"})
    return cards


def landed(value):
    m = re.match(r"(\d+) of \d+", str(value))
    return int(m.group(1)) if m else 0


def minutes(value):
    m = re.match(r"(\d+):(\d+)", str(value))
    return int(m.group(1)) + int(m.group(2)) / 60 if m else 0.0


def normalize(name):
    return re.sub(r"[^a-z ]", "", str(name).lower()).strip()


def fight_totals(stats):
    stats = stats.copy()
    stats["sig"] = stats["SIG.STR."].map(landed)
    stats["td"] = stats["TD"].map(landed)
    stats["ctrl"] = stats["CTRL"].map(minutes)
    stats["kd"] = pd.to_numeric(stats["KD"], errors="coerce").fillna(0)
    cols = ["sig", "td", "ctrl", "kd"]
    totals = stats.groupby(["EVENT", "BOUT", "FIGHTER"], as_index=False)[cols].sum()
    totals["key"] = totals["FIGHTER"].map(normalize)
    return totals


def build():
    download()
    results, stats, events = load()
    cards = parse_cards(results)
    print(f"parsed {len(cards)} judge cards from {cards['BOUT'].nunique()} decisions")

    agreement = ((cards["s1"] > cards["s2"]) == (cards["OUTCOME"] == "W/L")).mean()
    print(f"cards agreeing with the official result: {agreement:.1%} (the rest are dissenting split cards)")
    assert agreement > 0.85, "score orientation looks wrong"

    totals = fight_totals(stats)
    cards["key1"] = cards["f1"].map(normalize)
    cards["key2"] = cards["f2"].map(normalize)

    side1 = totals.rename(columns={"sig": "sig1", "td": "td1", "ctrl": "ctrl1", "kd": "kd1"})
    side2 = totals.rename(columns={"sig": "sig2", "td": "td2", "ctrl": "ctrl2", "kd": "kd2"})
    merged = cards.merge(side1, left_on=["EVENT", "BOUT", "key1"], right_on=["EVENT", "BOUT", "key"])
    merged = merged.merge(
        side2, left_on=["EVENT", "BOUT", "key2"], right_on=["EVENT", "BOUT", "key"], suffixes=("", "_b")
    )
    merged = merged.merge(events[["EVENT", "DATE"]], on="EVENT", how="left")
    print(f"joined {len(merged)} cards to fight stats")

    for v in ("sig", "td", "ctrl", "kd"):
        merged[f"{v}_diff"] = merged[f"{v}1"] - merged[f"{v}2"]
    merged["y"] = (merged["s1"] > merged["s2"]).astype(int)
    merged = merged[merged["s1"] != merged["s2"]]
    merged = merged[merged["DATE"] >= ERA_START]

    keep = ["DATE", "EVENT", "BOUT", "judge", "s1", "s2", "y",
            "sig_diff", "td_diff", "ctrl_diff", "kd_diff"]
    RESULTS_DIR.mkdir(exist_ok=True)
    merged[keep].to_csv(RESULTS_DIR / "judge_cards.csv", index=False)
    print(f"saved {len(merged)} cards from {ERA_START} onward to results/judge_cards.csv")


if __name__ == "__main__":
    build()
