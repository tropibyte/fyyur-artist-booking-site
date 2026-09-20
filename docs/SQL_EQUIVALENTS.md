# SQLAlchemy ↔ SQL

Every query in this app is written against the SQLAlchemy ORM. This page shows
what each one compiles to, so the SQL can be read and checked rather than taken
on trust.

The `SELECT` statements below are not transcribed by hand: run

```
flask sql-preview           # all of them
flask sql-preview search    # just the ones whose name contains "search"
```

and the application prints the statements exactly as psycopg2 will send them
(`sql_preview.py`). The listings here are those, with the long column lists of
whole-entity selects abbreviated to `...` for readability.

There is **no raw SQL anywhere in the request path**. The only hand-written SQL
in the project is one `setval()` call in `seed.py`, because resetting an
identity sequence is a Postgres administrative operation with no ORM
equivalent.

---

## SELECT and WHERE — search

`/venues/search`, `/artists/search`. Partial and case-insensitive, via `ILIKE`.

```python
# models.Venue.search -- the name/city branch
statement = (
    db.select(Venue.id, Venue.name, Venue.city, Venue.state,
              func.count(Show.id).filter(Show.start_time >= utcnow())
                  .label('num_upcoming_shows'))
    .outerjoin(Show, Show.venue_id == Venue.id)
    .group_by(Venue.id)
    .where(db.or_(Venue.name.ilike('%music%'), Venue.city.ilike('%music%')))
    .order_by(Venue.name)
)
```

```sql
SELECT "Venue".id, "Venue".name, "Venue".city, "Venue".state,
       count("Show".id) FILTER (WHERE "Show".start_time >= '2026-09-20 21:39:27+00') AS num_upcoming_shows
FROM "Venue" LEFT OUTER JOIN "Show" ON "Show".venue_id = "Venue".id
WHERE "Venue".name ILIKE '%music%' OR "Venue".city ILIKE '%music%'
GROUP BY "Venue".id
ORDER BY "Venue".name;
```

Searching `"San Francisco, CA"` takes the place branch of the same statement:

```sql
WHERE "Venue".city ILIKE 'San Francisco' AND "Venue".state = 'CA'
```

The `FILTER (WHERE ...)` aggregate is what lets one statement return both the
rows and their upcoming-show counts; the alternative — a count per row — is the
classic N+1.

---

## JOIN — "Past Performances" on a venue page

Rubric: *joins tables from existing models to select Artists by Venues where
they previously performed.*

```python
# models.Venue.shows_by_period
db.session.execute(
    db.select(Show, Artist)
    .join(Artist, Show.artist_id == Artist.id)
    .where(Show.venue_id == self.id)
    .order_by(Show.start_time)
).all()
```

```sql
SELECT "Show".id, "Show".artist_id, "Show".venue_id, "Show".start_time, ...,
       "Artist".id AS id_1, "Artist".name, "Artist".image_link, ...
FROM "Show" JOIN "Artist" ON "Show".artist_id = "Artist".id
WHERE "Show".venue_id = 1
ORDER BY "Show".start_time;
```

The rows are split into past and upcoming in Python against a single `now`, so
a show cannot land in both lists (or neither) because the clock ticked between
two queries.

## JOIN — "Venues Performed" on an artist page

```python
# models.Artist.shows_by_period
db.select(Show, Venue).join(Venue, Show.venue_id == Venue.id)
                      .where(Show.artist_id == 4)
                      .order_by(Show.start_time)
```

```sql
SELECT "Show".id, "Show".artist_id, "Show".venue_id, "Show".start_time, ...,
       "Venue".id AS id_1, "Venue".name, "Venue".image_link, ...
FROM "Show" JOIN "Venue" ON "Show".venue_id = "Venue".id
WHERE "Show".artist_id = 4
ORDER BY "Show".start_time;
```

## JOIN ×2 — the shows listing

```python
# models.Show.listing
db.select(Show, Artist, Venue)
  .join(Artist, Show.artist_id == Artist.id)
  .join(Venue, Show.venue_id == Venue.id)
  .order_by(Show.start_time.desc())
```

```sql
SELECT "Show"...., "Artist"...., "Venue"....
FROM "Show"
JOIN "Artist" ON "Show".artist_id = "Artist".id
JOIN "Venue"  ON "Show".venue_id  = "Venue".id
ORDER BY "Show".start_time DESC;
```

## LEFT JOIN + GROUP BY — venues grouped by area

```python
# models.Venue.grouped_by_area
Venue._listing_select().order_by(Venue.state, Venue.city, Venue.name)
```

```sql
SELECT "Venue".id, "Venue".name, "Venue".city, "Venue".state,
       count("Show".id) FILTER (WHERE "Show".start_time >= :now) AS num_upcoming_shows
FROM "Venue" LEFT OUTER JOIN "Show" ON "Show".venue_id = "Venue".id
GROUP BY "Venue".id
ORDER BY "Venue".state, "Venue".city, "Venue".name;
```

`LEFT OUTER JOIN` rather than `JOIN`: a venue with no shows still has to appear
on the page, with a count of zero.

## ORDER BY + LIMIT — recently listed

```python
# models.Artist.recent
db.select(Artist).order_by(Artist.created_at.desc(), Artist.id.desc()).limit(10)
```

```sql
SELECT "Artist".* FROM "Artist"
ORDER BY "Artist".created_at DESC, "Artist".id DESC
LIMIT 10;
```

`id DESC` is the tie-breaker: several rows seeded inside the same transaction
share a `created_at` to the microsecond, and without it the order is undefined.

---

## INSERT — creating a venue

```python
# controllers/venues.py + models.Venue.apply_form
venue = Venue().apply_form(form)      # sets columns and venue.genres
db.session.add(venue)
db.session.commit()
```

```sql
INSERT INTO "Venue" (name, city, state, address, phone, image_link,
                     facebook_link, website_link, seeking_description,
                     seeking_talent, created_at, updated_at)
VALUES ('The Gaslight', 'Austin', 'TX', '9 Rainey Street', '512-555-0100',
        'https://example.com/gaslight.jpg', NULL, NULL, 'Thursdays are open.',
        true, now(), now())
RETURNING "Venue".id;

INSERT INTO "VenueGenre" (venue_id, genre_id) VALUES (4, 2), (4, 17);
```

The genre rows come from `Genre.resolve()`, which looks the names up in one
`SELECT ... WHERE name IN (...)` rather than one query per genre.

## INSERT — booking a show

```python
show = Show(artist_id=form.artist_id.data,
            venue_id=form.venue_id.data,
            start_time=form.start_time.data)
db.session.add(show)
db.session.commit()
```

```sql
INSERT INTO "Show" (artist_id, venue_id, start_time, created_at, updated_at)
VALUES (6, 1, '2035-04-02 20:00:00+00', now(), now())
RETURNING "Show".id;
```

If a concurrent request booked the same artist for the same moment, this fails
on `uq_show_artist_start_time`; `controllers/helpers.commit()` catches the
`IntegrityError`, rolls back, and flashes *"That artist is already booked at
that date and time."*

## INSERT — an album and its tracks, one transaction

```python
album = Album(artist_id=5, name='Second Set', release_year=2026)
album.songs = [Song(title='Opener', track_number=1, duration_seconds=215), ...]
db.session.add(album)
db.session.commit()
```

```sql
INSERT INTO "Album" (artist_id, name, release_year, image_link, created_at, updated_at)
VALUES (5, 'Second Set', 2026, NULL, now(), now()) RETURNING "Album".id;

INSERT INTO "Song" (album_id, title, track_number, duration_seconds)
VALUES (7, 'Opener', 1, 215), (7, 'Closer', 2, 330);
```

## UPDATE — editing a record

```python
venue = db.get_or_404(Venue, venue_id)
venue.apply_form(form)
db.session.commit()
```

```sql
UPDATE "Venue"
SET name = 'The Musical Hop Renamed', updated_at = now()
WHERE "Venue".id = 1;

-- genre changes are a diff, not a rewrite:
DELETE FROM "VenueGenre" WHERE venue_id = 1 AND genre_id = 12;
INSERT INTO "VenueGenre" (venue_id, genre_id) VALUES (1, 3);
```

SQLAlchemy only writes the columns that actually changed, and only the junction
rows that were added or removed.

## DELETE — removing a venue

```python
venue = db.session.get(Venue, venue_id)
db.session.delete(venue)
db.session.commit()
```

```sql
DELETE FROM "Venue" WHERE "Venue".id = 2;
-- "Show" and "VenueGenre" rows go with it via ON DELETE CASCADE
```

Because the relationships are declared `passive_deletes=True`, SQLAlchemy does
*not* load the children first to delete them one at a time: the database does
the cascade in the same statement.

## The one piece of raw SQL

```python
# seed.py -- an identity sequence has no ORM representation
db.session.execute(text(
    'SELECT setval(pg_get_serial_sequence(\'"Venue"\', \'id\'), '
    'COALESCE((SELECT MAX(id) FROM "Venue"), 0) + 1, false)'
))
```

The demo rows carry hard-coded ids (`/venues/1`, `/artists/4`) so the seeded
catalogue matches the project brief; without resetting the sequence afterwards
the next form submission would try to reuse id 1.

---

## Running the statements yourself

```
psql -U fyyur -h 127.0.0.1 -d fyyur
```

```sql
-- the same "music" search, by hand
SELECT v.id, v.name, count(s.id) FILTER (WHERE s.start_time >= now())
FROM "Venue" v LEFT JOIN "Show" s ON s.venue_id = v.id
WHERE v.name ILIKE '%music%'
GROUP BY v.id;

-- prove the CHECK constraint is real
INSERT INTO "Venue" (name, city, state, address, seeking_talent, created_at, updated_at)
VALUES ('Nowhere', 'Atlantis', 'ZZ', '1 Deep St', false, now(), now());
-- ERROR:  new row for relation "Venue" violates check constraint "ck_venue_state"
```
