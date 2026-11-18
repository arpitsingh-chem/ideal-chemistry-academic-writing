# Reference: rule codes

The engine emits 115 rule codes across eight weighted dimensions. The authoritative list is
always the one the code produces:

```bash
python3 -m paperforge rules | head -3
```

```
115 rule codes
  CHEM-CHARGE-SYNTAX
  CHEM-DBE-FRACTION
  ...
```

Do not rely on a list copied into documentation — including this page. Regenerate it.

## Dimensions and weights

| Dimension | Weight | What it covers |
|---|---|---|
| structure | 15 % | title, abstract presence/splitting, section grammar and order |
| abstract | 10 % | word limits for the *resolved* article type, the five moves |
| evidence | 20 % | formula↔HRMS, yield↔mass, NMR H-count, CCDC, purity claims |
| references | 15 % | missing keys, unresolvable DOIs, **retractions**, duplicates, style |
| figures | 10 % | dpi, physical width vs column width, TOC aspect ratio |
| journal | 15 % | abstract/body caps, page caps, required statements per publisher |
| ethics | 10 % | CRediT, COI, funding, data availability, AI disclosure, safety |
| style | 5 % | hype words, hedging density, sentence-length variation, units |

## Scoring

```
score = 100 − 12·errors − 4·warnings − 0.5·notes      any critical finding caps at 55
≥ 90 submission-ready · ≥ 75 minor revision · ≥ 60 major revision
```

Grades: A+ ≥ 95 · A ≥ 90 · B ≥ 80 · C ≥ 70 · D ≥ 60 · F below.

## Code prefixes

| Prefix | Area |
|---|---|
| `STR-` | manuscript structure |
| `EVI-` | evidence completeness and cross-checks |
| `CHEM-` | chemistry arithmetic and valence |
| `REF-` | references and citation hygiene |
| `FIG-`, `TAB-`, `TOC-` | display items |
| `JNL-` | journal-specific limits |
| `ETH-` | ethics and required statements |
| `STY-`, `GRD-` | style and grounding |
| `FILE-` | input file problems |

## Chemistry codes worth knowing

| Code | Severity | Meaning |
|---|---|---|
| `CHEM-FORMULA` | error | the formula cannot be parsed |
| `CHEM-DBE-NEG` | error / info | negative DBE (info when a valence is variable or the species is charged) |
| `CHEM-DBE-FRACTION` | error / info | half-integer DBE for a neutral fixed-valence formula |
| `CHEM-DBE-METAL` | info | DBE undefined for a metal-containing formula |
| `CHEM-CHARGE-SYNTAX` | warn | ambiguous attached charge (`SO42-`) — write `SO4 2-` |
| `CHEM-HRMS-CALCD` | error | the reported calcd mass is inconsistent with the formula/adduct |
| `CHEM-HRMS-PPM` | error | found vs calcd outside the ppm window |
| `CHEM-YIELD-MASS` | error | mass, mmol and % yield disagree |
| `CHEM-NMR-H` | error / warn | ¹H integrals do not sum to the formula's H count |
| `CHEM-NMR-C` | error | more ¹³C signals than carbons |
| `CHEM-NRULE` | warn | nitrogen rule violated (neutral species only) |

See `../explanations/verification-model.md` for what a passing score does and does not
assert.
