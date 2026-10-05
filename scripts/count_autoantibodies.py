"""Exploratory signal check: how often do case-report abstracts mention
autoantibody / serology tests?

Regex count over title + abstract of the committed processed JSONL. Not an
extraction feature: matches include background definitions and negative
panels, so "positive-result sentence" is an upper bound on cases where
serology actually resolved the misdiagnosis.

Usage: python3 scripts/count_autoantibodies.py [data/nlp/processed/*.jsonl ...]
"""
import argparse
import collections
import glob
import json
import re

# Short acronyms (ANA, Sm) are matched case-sensitively to avoid hitting
# ordinary words; everything else is case-insensitive.
ANTIBODIES = {
    "ANA": (r"\bANA\b|[Aa]ntinuclear antibod", 0),
    "anti-dsDNA": (r"(anti-?\s?)?ds-?DNA", re.I),
    "anti-Sm": (r"anti-?\s?Sm\b|anti-?Smith", 0),
    "anti-Ro/SSA": (r"anti-?\s?(Ro|SSA)\b|\bSS-?A\b|\bRo52|\bRo60", re.I),
    "anti-La/SSB": (r"anti-?\s?(La|SSB)\b|\bSS-?B\b", re.I),
    "anti-U1-RNP": (r"U1-?\s?(sn)?RNP|anti-?\s?RNP", re.I),
    "antiphospholipid": (r"anticardiolipin|lupus anticoagulant|beta-?2-?glycoprotein|β2-?glycoprotein|antiphospholipid antibod", re.I),
    "ANCA/PR3/MPO": (r"\bANCA\b|\bPR3\b|\bMPO\b|proteinase 3|myeloperoxidase", re.I),
    "AQP4": (r"AQP-?4|aquaporin", re.I),
    "AChR/MuSK": (r"\bAChR\b|acetylcholine receptor|\bMuSK\b", re.I),
    "complement": (r"\bC3\b|\bC4\b|hypocomplement|complement", re.I),
    "other anti-X antibody": (r"\banti-[A-Za-z0-9]+ antibod", re.I),
}
RESULT_WORDS = re.compile(r"positiv|reveal|confirm|detect|elevat|high titer|titre|titer|serolog", re.I)


def find(name: str, text: str) -> bool:
    pattern, flags = ANTIBODIES[name]
    return re.search(pattern, text, flags) is not None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("jsonl", nargs="*", default=sorted(glob.glob("data/nlp/processed/*.jsonl")))
    args = parser.parse_args()

    for path in args.jsonl:
        records = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
        n = len(records)
        mentions = with_result = misdx = misdx_mentions = 0
        by_type: collections.Counter[str] = collections.Counter()
        for r in records:
            text = f"{r.get('title') or ''}. {r.get('abstract') or ''}"
            hits = {name for name in ANTIBODIES if find(name, text)}
            has_misdx = bool(r.get("misdiagnosis_sequence"))
            misdx += has_misdx
            if not hits:
                continue
            mentions += 1
            misdx_mentions += has_misdx
            by_type.update(hits)
            sentences = re.split(r"(?<=[.!?])\s+", text)
            if any(RESULT_WORDS.search(s) and any(find(h, s) for h in hits) for s in sentences):
                with_result += 1

        print(f"\n{path.split('/')[-1]}: {n} records")
        print(f"  any antibody/serology mention: {mentions} ({mentions / n:.0%})")
        print(f"  with a positive-result sentence: {with_result} ({with_result / n:.0%})")
        print(f"  among {misdx} misdiagnosis records: {misdx_mentions} ({misdx_mentions / max(misdx, 1):.0%})")
        print(f"  by type: {dict(by_type.most_common())}")


if __name__ == "__main__":
    main()
