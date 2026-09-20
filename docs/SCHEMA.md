# Fyyur data model

## Entity relationship diagram

```
                       +-----------------+
                       |      Genre      |
                       +-----------------+
                       | id      PK      |
                       | name    UNIQUE  |
                       +--------+--------+
                                |
             +------------------+------------------+
             | (M:N)                               | (M:N)
     +-------+--------+                    +-------+--------+
     |   VenueGenre   |                    |  ArtistGenre   |
     +----------------+                    +----------------+
     | venue_id  PK/FK|                    | artist_id PK/FK|
     | genre_id  PK/FK|                    | genre_id  PK/FK|
     +-------+--------+                    +-------+--------+
             |                                     |
     +-------+--------+                    +-------+---------+
     |     Venue      |                    |     Artist      |
     +----------------+                    +-----------------+
     | id        PK   |                    | id        PK    |
     | name           |                    | name            |
     | city, state    |                    | city, state     |
     | address        |                    | phone           |
     | phone          |                    | image_link      |
     | image_link     |                    | facebook_link   |
     | facebook_link  |                    | website_link    |
     | website_link   |                    | seeking_venue   |
     | seeking_talent |                    | seeking_desc.   |
     | seeking_desc.  |                    | created_at      |
     | created_at     |                    | updated_at      |
     | updated_at     |                    +--+----+-----+---+
     +-------+--------+                       |    |     |
             |  1                           1 |    | 1   | 1
             |                                |    |     |
             |          +-----------------+   |    |     |
             +----------+      Show       +---+    |     |
                      * +-----------------+ *      |     |
                        | id        PK    |        |     |
                        | artist_id FK    |        |     |
                        | venue_id  FK    |        |     |
                        | start_time      |        |     |
                        | created_at      |        |     |
                        | updated_at      |        |     |
                        +-----------------+        |     |
                                                   |     |
                    +-----------------+            |     |
                    |  Availability   +------------+     |
                    +-----------------+  *               |
                    | id        PK    |                  |
                    | artist_id FK    |                  |
                    | start_time      |                  |
                    | end_time        |                  |
                    +-----------------+                  |
                                                         |
                    +-----------------+                  |
                    |      Album      +------------------+
                    +-----------------+  *
                    | id        PK    |
                    | artist_id FK    |
                    | name            |
                    | release_year    |
                    | image_link      |
                    +--------+--------+
                             | 1
                             |
                             | *
                    +--------+--------+
                    |      Song       |
                    +-----------------+
                    | id        PK    |
                    | album_id  FK    |
                    | title           |
                    | track_number    |
                    | duration_seconds|
                    +-----------------+
```

## Relationship types, and why each one is what it is

| Relationship | Type | Why |
|---|---|---|
| Artist ↔ Venue | **many-to-many**, through `Show` | An artist plays many venues over time and a venue books many artists. Neither side can hold a foreign key to the other. |
| Artist → Show, Venue → Show | **one-to-many** | `Show` is the *association object* of the many-to-many above. It gets its own table (rather than a bare junction table) because the association carries an attribute of its own — `start_time` — and because a show is a thing the app lists, links to and counts. |
| Venue ↔ Genre, Artist ↔ Genre | **many-to-many**, through `VenueGenre` / `ArtistGenre` | A venue has several genres and a genre belongs to many venues. Genres are a shared vocabulary, not a property of one row. |
| Artist → Availability | **one-to-many** | An artist publishes several bookable windows; a window belongs to exactly one artist. |
| Artist → Album → Song | **one-to-many**, twice | A discography is a strict hierarchy here: this app models an album as belonging to a single artist. (A real catalogue would need a many-to-many for collaborations; that is a deliberate scope decision, not an oversight.) |

## Normalisation

**First normal form** — every column holds a single, atomic value. The one
place this is easy to get wrong is genres. A `genres VARCHAR` column holding
`"Jazz,Reggae,Swing"`, or a `genres TEXT[]` array, packs a repeating group into
one field: you cannot join on it, you cannot index it usefully, "rename Hip-Hop
to Hip Hop" becomes a string rewrite of every row, and a typo creates a new
genre silently. Genres therefore live in their own table, joined through
`VenueGenre` / `ArtistGenre`.

**Second normal form** — no non-key column depends on only part of a composite
key. The only composite keys in the schema are the two junction tables, and
they carry no columns beyond their key.

**Third normal form** — no non-key column depends on another non-key column.
Two cases are worth naming:

* `city` and `state` are stored on `Venue`/`Artist` rather than in a `City`
  table. `state` is not functionally dependent on `city` (there is a Portland
  in Oregon and one in Maine), so this does not violate 3NF.
* `Song.duration_seconds` is stored, `Song.duration` (`m:ss`) is computed in
  Python. Storing both would be a derived-value dependency.

`Show` stores no denormalised copies of the artist's or venue's name or image —
the detail pages join for those, so a rename is visible everywhere immediately.

## Constraints

Every rule the forms enforce also exists in the database, because form
validation is advice and a constraint is a guarantee. Two requests racing each
other both pass a Python check; only one wins a unique index.

### Required (NOT NULL)

`Venue`: `name`, `city`, `state`, `address`, `seeking_talent`, `created_at`,
`updated_at`.
`Artist`: `name`, `city`, `state`, `seeking_venue`, `created_at`, `updated_at`.
`Show`: `artist_id`, `venue_id`, `start_time`.
`Availability`: `artist_id`, `start_time`, `end_time`.
`Album`: `artist_id`, `name`. `Song`: `album_id`, `title`. `Genre`: `name`.

### Unique

| Constraint | Meaning |
|---|---|
| `uq_venue_name_address` (`name`, `address`, `city`, `state`) | One listing per room at an address. |
| `uq_artist_name_city` (`name`, `city`, `state`) | Two acts may share a name in different towns, not in one town. |
| `uq_show_artist_start_time` (`artist_id`, `start_time`) | An artist cannot be in two places at once. |
| `uq_availability_window` (`artist_id`, `start_time`, `end_time`) | No duplicate windows. |
| `uq_album_artist_name` (`artist_id`, `name`) | One album title per artist. |
| `uq_song_album_title`, `uq_song_album_track` | No duplicate titles or track numbers within an album. |
| `Genre.name` | The vocabulary is a set. |

### Check

| Constraint | Rule |
|---|---|
| `ck_venue_state`, `ck_artist_state` | `state` ∈ the 50 states + DC. |
| `ck_genre_name_allowed` | `Genre.name` ∈ the canonical genre list. |
| `ck_venue_name_present`, `ck_artist_name_present` | A name cannot be blank or whitespace. |
| `ck_venue_seeking_description`, `ck_artist_seeking_description` | Saying "seeking talent/venues" requires saying what for. |
| `ck_availability_order` | A window ends after it starts. |
| `ck_album_release_year` | 1877 (the first sound recording) to 2100. |
| `ck_song_track_number`, `ck_song_duration` | Positive when present. |

### Referential integrity

All foreign keys are `NOT NULL` and declared `ON DELETE CASCADE`, except the
junction tables' reference to `Genre`, which is `ON DELETE RESTRICT` — deleting
a venue should take its tags with it, but deleting a *genre* that is still in
use should fail rather than silently untag half the catalogue.

The ORM relationships mirror this with `cascade='all, delete-orphan'` and
`passive_deletes=True`, so a delete is one SQL statement and the database does
the cascading, instead of SQLAlchemy loading every child row to delete it
individually.

### Indexes

Primary keys and unique constraints are indexed automatically. Added on top:

* `ix_venue_name_lower`, `ix_artist_name_lower` — functional indexes on
  `lower(name)`, which is what case-insensitive `ILIKE` search needs.
* `ix_venue_city_state`, `ix_artist_city_state` — the "San Francisco, CA"
  search path.
* `Show.artist_id`, `Show.venue_id`, `Show.start_time` — every detail page and
  the upcoming/past split.
* `created_at` on each entity — the home page's "recently listed" ordering.

## Design decisions worth defending

**`state` is a CHECK constraint, not a native Postgres `ENUM`.** Both enforce
the same set. A CHECK constraint can be changed in a one-line migration;
`ALTER TYPE ... ADD VALUE` cannot run inside a transaction block, which makes
enum changes awkward to roll back and awkward for Alembic to autogenerate.

**Genres are a table, not an enum or an array.** The vocabulary is seeded from
`constants.GENRES` by `flask seed-genres`, and `ck_genre_name_allowed` keeps a
stray insert from inventing a genre. This keeps the referential benefits of a
lookup table and the closed-set guarantee of an enum.

**All timestamps are `TIMESTAMP WITH TIME ZONE`.** Show times are absolute
moments, and a booking site that stores them naively breaks the first time two
users are in different zones. The application works in UTC throughout; form
input with no offset is interpreted as UTC (`forms.as_utc`).

**`Show` does not enforce "one artist per venue per slot".** A venue can run a
double bill, so `(venue_id, start_time)` is intentionally *not* unique, while
`(artist_id, start_time)` is.
