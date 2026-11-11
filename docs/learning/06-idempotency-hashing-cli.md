# 06 — Idempotency, hashing and a CLI

## The concept in plain words
- **Idempotent** means doing it twice has the same effect as doing it once. `fetch` can run
  every hour, after a crash, or by accident twice: the database ends up the same. This is the
  most useful property a scheduled job can have.
- **Hashing for identity**: the same job appears on several boards with different ids. We
  *normalize* company + title (lowercase, drop punctuation) and hash it with SHA-1. Equal text
  gives an equal 40-character key. We hash so the key is short and the same size every time,
  not for security.
- **Let the database enforce it**: a `UNIQUE INDEX` on `dedupe_key` plus `INSERT OR IGNORE` means
  SQLite itself refuses duplicates. Python can't forget to check, and it's safe even if two
  fetches run at once.
- **A CLI with argparse**: `python -m jobpilot fetch` runs `__main__.py`. argparse parses
  subcommands and options, and generates `--help` and `--version` for free. `main()` returns an exit
  code: 0 = ok, 1 = every source failed, 2 = config error. That's what schedulers check.

## Why we used it here
- The live run fetched 586 jobs, matched 29 and stored 27: 2 WWR jobs were already stored from
  another board. The second run stored 0.
- Each source runs in its own `try`: one site being down shows `ERROR` in its row, and the rest still save.
- The filter is a deliberately **coarse first pass** (keywords in title, place in location, minus
  excluded regions like "US only"). The AI scoring in M3 does the nuanced ranking.

## .NET equivalent
| Python | .NET |
|---|---|
| idempotent `INSERT OR IGNORE` + unique index | `INSERT ... WHERE NOT EXISTS` / EF Core unique index + catch `DbUpdateException` |
| `hashlib.sha1(text.encode()).hexdigest()` | `Convert.ToHexString(SHA1.HashData(Encoding.UTF8.GetBytes(text)))` |
| `argparse` subcommands | `System.CommandLine` `RootCommand` + `Command("fetch")` |
| `python -m jobpilot fetch` | `dotnet run -- fetch` |
| `sys.exit(main())` exit code | `return exitCode;` from `Main` |

```mermaid
flowchart LR
    S1[remotive] & S2[remoteok] & S3[arbeitnow] & S4[wwr] --> F{matches?<br/>role · location · not excluded}
    F -- no --> X[dropped]
    F -- yes --> K[dedupe_key = sha1 company|title]
    K --> DB[(INSERT OR IGNORE<br/>UNIQUE dedupe_key)]
    DB --> C[counts table]
```

## Self-check
1. Why is it safer to rely on a UNIQUE index than on checking "does it exist?" in Python first?
2. Why do we normalize text before hashing it?
3. What exit code does `fetch` return when one source fails but others succeed, and why?
