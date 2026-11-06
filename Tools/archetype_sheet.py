"""Write a set's auto-built archetype sheet so you can edit it.

    python Tools/archetype_sheet.py --dataset Sets/FRA_PremierDraft_All_Data.json --set FRA

Writes Sets/Archetypes/<SET>.auto.json listing, for each color pair, the cards
the Archetype Lens treats as key cards and the themes it found. To change what
the lens uses, copy it to Sets/Archetypes/<SET>.json and edit it:

- "name": a label for the archetype, shown in the advisor's reasons
- "key_cards": card names to count as key cards for that pair
- "themes": card tags (e.g. synergy_graveyard, token_maker) the pair rewards
- "replace": true to use only your list for that pair, false to add to the auto list

The app reads Sets/Archetypes/<SET>.json the next time it loads the set.
"""

import argparse
import gzip
import os
import shutil
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", required=True, help="The set's dataset (.json or .json.gz)")
    parser.add_argument("--set", required=True, help="Set code, e.g. FRA")
    args = parser.parse_args(argv)

    from src.dataset import Dataset
    from src.advisor.archetype_lens import ArchetypeSheet

    dataset = Dataset()
    path = args.dataset
    with tempfile.TemporaryDirectory() as tmp:
        if path.endswith(".gz"):
            plain = os.path.join(tmp, "dataset.json")
            with gzip.open(path, "rb") as src, open(plain, "wb") as dst:
                shutil.copyfileobj(src, dst)
            path = plain
        dataset.open_file(path)
    ratings = dataset.get_card_ratings()
    if not ratings:
        raise SystemExit(f"No card ratings in {args.dataset}")

    sheet = ArchetypeSheet.build(ratings, args.set)
    out = sheet.write_sheet_template(args.set)
    for pair, entry in sheet.pairs.items():
        cards = ", ".join(list(entry.get("key_cards", {}))[:5]) or "(none)"
        themes = ", ".join(entry.get("themes", [])) or "-"
        print(f"{pair}: {cards} | themes: {themes}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
