# Google Sheet schema

One spreadsheet, four tabs. Tab names must match exactly (lowercase).
Row 1 is the header row. Empty rows are ignored.

Only `days`, `stops` and `places` are exported to the website. `bookings` never leaves
the sheet; the site links back to it instead.

## `days`  (exported)

| column       | example                          | notes                                    |
|--------------|----------------------------------|------------------------------------------|
| day          | 7                                | integer, drives ordering                 |
| date         | 2026-10-30                       | ISO date, or leave blank until fixed     |
| title        | Te Anau to Franz Josef           | short heading                            |
| leg          | West Coast                       | groups days into sections on the page    |
| from         | Te Anau                          | town we wake up in                       |
| to           | Franz Josef                      | town we sleep in                         |
| drive_time   | 6h30                             | free text, shown as a chip               |
| notes        | Blue Pools on the way over...    | paragraph, plain text                    |
| sheet_row    | (leave blank)                    | filled by the script, ignore             |

## `stops`  (exported)

| column | example                                   | notes                                        |
|--------|-------------------------------------------|----------------------------------------------|
| day    | 8                                         | which day it belongs to                      |
| name   | Wakefield Bakery                          |                                              |
| type   | food / walk / drive / activity / booked   | free text, used for an icon                  |
| link   | https://...                               | optional, public URL only                    |
| notes  | 30min short of Nelson, worth holding out  | optional                                     |
| place  | Wakefield                                 | optional, a name from the `places` tab, puts a pin on the map |

## `places`  (exported)

The gazetteer. Every town or stop the itinerary mentions, with coordinates so
the map can draw the route. `from` and `to` in `days` and `place` in `stops`
must match a `name` here exactly.

| column | example                                  | notes                                              |
|--------|------------------------------------------|----------------------------------------------------|
| name   | Punakaiki                                | the key other tabs reference                       |
| lat    | -42.1103                                 | decimal degrees                                    |
| lng    | 171.3315                                 |                                                    |
| kind   | city / town / stop                       | town = somewhere we sleep, stop = somewhere we pass |
| photo  | Pancake Rocks, Punakaiki.jpg             | optional, a Wikimedia Commons file name            |
| blurb  | Pancake Rocks and the Truman Track       | optional, one line for the card                    |

Grab coordinates by right-clicking a spot in Google Maps and clicking the
numbers at the top of the popup. Accuracy to a few hundred metres is plenty.

## `bookings`  (private, NOT exported)

| column       | example                     |
|--------------|-----------------------------|
| day          | 3                           |
| place        | Airbnb, Queenstown          |
| address      | 12 Example St, Fernhill     |
| confirmation | HMABC123                    |
| check_in     | 15:00                       |
| notes        | lockbox code in WhatsApp    |

The site shows "Queenstown" for that day and a button that deep-links to this
tab, so the address is only ever visible to people the sheet is shared with.
