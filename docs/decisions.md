# Decisions

## Sentiment model — 2026-05-23 (Phase 4)

**Chosen: `cardiffnlp/twitter-xlm-roberta-base-sentiment`**
(revision `f2f1202b1bdeb07342385c3f807f9c07cd8f5cf8`, pinned in `config.py`).
Fallback: `tabularisai/multilingual-sentiment-analysis`.

**Method:** ran both candidates on 40 random *analyzable* comments from the real
account via `scripts/sentiment_compare.py`. Models agreed on 21/40 (52%).

**Why cardiffnlp:**
- It correctly read genuine positives, emoji, and Indonesian compliments that
  tabularisai mislabeled **negative** — e.g. `Lagu sukaankuuuuuuuu 😍😍`,
  `Ih kok ganteng sih kameranya 😌`, `Bahagiaaaaaaa`, `keren2 lh pada`.
- tabularisai's failure mode (compliments → negative) is the more damaging one
  for an audience-facing dashboard: it makes a warm comment section look hostile,
  which is exactly the credibility risk R1 warns about.
- cardiffnlp's weakness is over-reading **negative** on terse slang (`O gt`,
  `Parah`, `Blaasss`). Accepted tradeoff — the US-4 sanity-check modal lets the
  user and audience inspect any bucket's actual comments (B4).
- Not a rigorous 100-comment gold-labeled accuracy test (plan's ideal); a 40-row
  human eyeball was enough to see the decisive difference. Revisit if dogfooding
  shows the buckets feel wrong.

**Toolchain note (R8):** `transformers` is pinned to `<5`. transformers 5.x
mis-routes XLM-RoBERTa's SentencePiece tokenizer through the tiktoken parser and
crashes. cardiffnlp also requires `sentencepiece` + `protobuf` (both in the `ml`
extra).
