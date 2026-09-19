"""
zone_reader.py -- documents `db/zone.cfg` (81 bytes, plain text), the
very last file on the disc this project had never actually opened
(previously only noted as "not part of files.cfg's compressed-data
model, no SIEMENS header" -- flagged but never read). IDENTIFIED
(real, plain-text content confirmed); the per-digit zone/country
mapping is NOT decoded.

============================================================================
Content -- CONFIRMED, plain text, one line
============================================================================
The entire file is one line (81 bytes including the trailing newline):

    eeu = 10.1/DB 01234 18408555 44444444444444434441111444444444214114442222444444

`eeu` matches the disc's own dataset name (every `eeu.*`/`eeuz.*` file,
README S3). `18408555` ends in `8555` -- this reference disc's own
volume number (`CD_8555`, matching `cdrom.toc`'s own `Volume: CD_8555`
line, research/create_cd_reader.py) -- consistent with this being a
disc-specific (not dataset-generic) config value; the leading `1840`
prefix wasn't matched against any other identifier found this session.
`10.1/DB` and `01234` were not matched against anything either.

The trailing 50-character digit string (`4444444444444443444111144444444
4214114442222444444`) is a real, structured value: mostly `4` (37/50,
74%), with a handful of `1`s (7), `2`s (5), and a single `3`. 50 doesn't
match any of this project's own already-established per-country (35,
`eeu.ctr`/`eeu.cal`) or per-timeinfo (13, `eeu.ti`) counts exactly, so
it isn't a direct 1:1 country or DST-zone list under those existing
countings. The overall SHAPE (one dominant value covering ~74% of
positions, several rare minority values) is qualitatively similar to
`eeu.ti`'s own `timeinfo_id` distribution (id=1 covers 72% of counties,
README S3.22) -- plausibly a related, but not confirmed identical,
per-region zone/DST assignment concept. Not decoded further.

============================================================================
Practical use
============================================================================
Plain text, read directly -- no parsing function provided.
"""
