# Reference: command line

Generated from `paperforge <command> --help` on the current build, so it cannot drift
from the implementation. Exit codes: `0` OK · `1` gate failed or a provider was
unavailable · `2` bad input.

## Top level

```
usage: paperforge [-h] [--version]
                  {context,ingest,new,journals,refs,figures,draft,check,score,si,cover-letter,bundle,retarget,rules,scheme,research,institution,doctor,llm-draft} ...

PaperForge — a chemistry-aware manuscript engine: compose, verify, score and
package a paper.

positional arguments:
  {context,ingest,new,journals,refs,figures,draft,check,score,si,cover-letter,bundle,retarget,rules,scheme,research,institution,doctor,llm-draft}
    context             print the grounded evidence pack for an LLM
    ingest              turn a folder of data/figures/refs into a project
    new                 scaffold a new paper project
    journals            journal database: list/search/match/show
    refs                reference verification
    figures             figure inventory and TOC rendering
    draft               compose the manuscript
    check               run the full rule set
    score               submission-readiness score (0–100)
    si                  render Supporting Information
    cover-letter        render the cover letter
    bundle              build a submission zip
    retarget            what changes if I submit elsewhere?
    rules               list every rule code
    scheme              draw reaction schemes / TOC graphics from SMILES
    research            global research intelligence (providers, sync,
                        coverage)
    institution         the preserved IISER Bhopal institutional collection
    doctor              environment check
    llm-draft           optional LLM pass over the grounded outline

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
```

## `new`

```
usage: paperforge new [-h] [--title TITLE] [--journal JOURNAL] path

positional arguments:
  path

options:
  -h, --help         show this help message and exit
  --title TITLE
  --journal JOURNAL
```

## `ingest`

```
usage: paperforge ingest [-h] [--out OUT] [--title TITLE] [--journal JOURNAL]
                         [--article-type ARTICLE_TYPE] [--json]
                         source

positional arguments:
  source

options:
  -h, --help            show this help message and exit
  --out OUT             project directory (default: in place)
  --title TITLE
  --journal JOURNAL
  --article-type ARTICLE_TYPE
  --json
```

## `context`

```
usage: paperforge context [-h] [--compact] path

positional arguments:
  path

options:
  -h, --help  show this help message and exit
  --compact
```

## `check`

```
usage: paperforge check [-h] [--file FILE] [--journal JOURNAL]
                        [--article-type ARTICLE_TYPE] [--json] [--verbose]
                        [--verify-refs] [--offline]
                        [path]

positional arguments:
  path

options:
  -h, --help            show this help message and exit
  --file FILE           check an existing .tex/.md/.docx instead of a project
  --journal JOURNAL
  --article-type ARTICLE_TYPE
  --json
  --verbose
  --verify-refs         query Crossref for every DOI
  --offline
```

## `score`

```
usage: paperforge score [-h] [--journal JOURNAL] [--article-type ARTICLE_TYPE]
                        [--json] [--verify-refs] [--offline] [--min MIN]
                        [path]

positional arguments:
  path

options:
  -h, --help            show this help message and exit
  --journal JOURNAL
  --article-type ARTICLE_TYPE
  --json
  --verify-refs
  --offline
  --min MIN
```

## `draft`

```
usage: paperforge draft [-h]
                        [--format {md,tex,docx,txt,all} [{md,tex,docx,txt,all} ...]]
                        [--out OUT] [--journal JOURNAL]
                        [--article-type ARTICLE_TYPE] [--cover-letter]
                        [--highlights]
                        [path]

positional arguments:
  path

options:
  -h, --help            show this help message and exit
  --format {md,tex,docx,txt,all} [{md,tex,docx,txt,all} ...]
  --out OUT
  --journal JOURNAL
  --article-type ARTICLE_TYPE
  --cover-letter
  --highlights
```

## `si`

```
usage: paperforge si [-h] [--out OUT] [path]

positional arguments:
  path

options:
  -h, --help  show this help message and exit
  --out OUT
```

## `figures`

```
usage: paperforge figures [-h] [--source SOURCE] [--out OUT]
                          [--journal JOURNAL] [--article-type ARTICLE_TYPE]
                          {inventory,toc} [path]

positional arguments:
  {inventory,toc}
  path

options:
  -h, --help            show this help message and exit
  --source SOURCE
  --out OUT
  --journal JOURNAL
  --article-type ARTICLE_TYPE
```

## `scheme`

```
usage: paperforge scheme [-h] [--conditions [CONDITIONS ...]]
                         [--yield-text YIELD_TEXT] [--labels LABELS]
                         [--caption CAPTION] [--arrow ARROW]
                         [--journal JOURNAL] [--out OUT]
                         {reaction,toc} reaction

positional arguments:
  {reaction,toc}
  reaction              'reactant>>product' (dot-separate multiple structures)

options:
  -h, --help            show this help message and exit
  --conditions [CONDITIONS ...]
  --yield-text YIELD_TEXT
  --labels LABELS
  --caption CAPTION
  --arrow ARROW
  --journal JOURNAL
  --out OUT
```

## `journals`

```
usage: paperforge journals [-h] [--top TOP] [--family FAMILY]
                           [--article-type ARTICLE_TYPE]
                           {list,search,match,show} [query ...]

positional arguments:
  {list,search,match,show}
  query

options:
  -h, --help            show this help message and exit
  --top TOP
  --family FAMILY
  --article-type ARTICLE_TYPE
```

## `refs`

```
usage: paperforge refs [-h] [--mailto MAILTO] [--offline]
                       {verify,add,check} path [dois ...]

positional arguments:
  {verify,add,check}
  path
  dois

options:
  -h, --help          show this help message and exit
  --mailto MAILTO
  --offline
```

## `retarget`

```
usage: paperforge retarget [-h] --to TO [--article-type ARTICLE_TYPE] [path]

positional arguments:
  path

options:
  -h, --help            show this help message and exit
  --to TO
  --article-type ARTICLE_TYPE
```

## `bundle`

```
usage: paperforge bundle [-h] [--out OUT] [--journal JOURNAL]
                         [--article-type ARTICLE_TYPE] [--strict]
                         [--fail-on {blocker,error,warn}]
                         [--min-score MIN_SCORE] [--no-verify] [--offline]
                         [path]

positional arguments:
  path

options:
  -h, --help            show this help message and exit
  --out OUT
  --journal JOURNAL
  --article-type ARTICLE_TYPE
  --strict              refuse to bundle if the fail-on level is hit
  --fail-on {blocker,error,warn}
  --min-score MIN_SCORE
  --no-verify
  --offline
```

## `rules`

```
usage: paperforge rules [-h]

options:
  -h, --help  show this help message and exit
```

## `doctor`

```
usage: paperforge doctor [-h]

options:
  -h, --help  show this help message and exit
```

## `research`

```
usage: paperforge research [-h]
                           {providers,search,fetch,sync,coverage,export,dedup} ...

positional arguments:
  {providers,search,fetch,sync,coverage,export,dedup}
    providers           list adapters, capabilities and known-unavailable
                        sources
    search              search every configured source at once
    fetch               resolve one DOI across providers and reconcile
    sync                synchronise a query into the local research store
    coverage            transparent coverage report
    export              export a clean dataset + coverage sidecar
    dedup               show duplicate proposals without merging

options:
  -h, --help            show this help message and exit
```

## `institution`

```
usage: paperforge institution [-h] {stats,search,faculty,journals} ...

positional arguments:
  {stats,search,faculty,journals}
    stats               collection statistics (offline snapshot)
    search              search the institutional snapshot
    faculty             works by one faculty member
    journals            venues ranked by captured output

options:
  -h, --help            show this help message and exit
```

### `research` sub-commands

#### `research providers`

```
usage: paperforge research providers [-h] [--json] [--all-ok]

options:
  -h, --help  show this help message and exit
  --json
  --all-ok    accepted for symmetry; readiness is always reported
```

#### `research search`

```
usage: paperforge research search [-h] [--source SOURCE] [--limit LIMIT]
                                  [--from-year FROM_YEAR] [--json]
                                  query

positional arguments:
  query

options:
  -h, --help            show this help message and exit
  --source SOURCE       restrict to a provider (repeatable)
  --limit LIMIT
  --from-year FROM_YEAR
  --json
```

#### `research fetch`

```
usage: paperforge research fetch [-h] [--source SOURCE] [--json] identifier

positional arguments:
  identifier       DOI, arXiv id or PMID

options:
  -h, --help       show this help message and exit
  --source SOURCE
  --json
```

#### `research sync`

```
usage: paperforge research sync [-h] [--db DB] [--source SOURCE]
                                [--limit LIMIT] [--from-year FROM_YEAR]
                                [--dry-run] [--json]
                                query

positional arguments:
  query

options:
  -h, --help            show this help message and exit
  --db DB
  --source SOURCE
  --limit LIMIT
  --from-year FROM_YEAR
  --dry-run             do everything except write
  --json
```

#### `research coverage`

```
usage: paperforge research coverage [-h] [--db DB] [--json]

options:
  -h, --help  show this help message and exit
  --db DB
  --json
```

#### `research export`

```
usage: paperforge research export [-h] [--db DB] --out OUT
                                  [--format {json,csv}]

options:
  -h, --help           show this help message and exit
  --db DB
  --out OUT
  --format {json,csv}
```

#### `research dedup`

```
usage: paperforge research dedup [-h] [--db DB] [--threshold THRESHOLD]
                                 [--json]

options:
  -h, --help            show this help message and exit
  --db DB
  --threshold THRESHOLD
  --json
```

### `institution` sub-commands

#### `institution stats`

```
usage: paperforge institution stats [-h] [--json]

options:
  -h, --help  show this help message and exit
  --json
```

#### `institution search`

```
usage: paperforge institution search [-h] [--limit LIMIT] [--json] query

positional arguments:
  query

options:
  -h, --help     show this help message and exit
  --limit LIMIT
  --json
```

#### `institution faculty`

```
usage: paperforge institution faculty [-h] [--limit LIMIT] [--json] query

positional arguments:
  query

options:
  -h, --help     show this help message and exit
  --limit LIMIT
  --json
```

#### `institution journals`

```
usage: paperforge institution journals [-h] [--limit LIMIT] [--json]

options:
  -h, --help     show this help message and exit
  --limit LIMIT
  --json
```

