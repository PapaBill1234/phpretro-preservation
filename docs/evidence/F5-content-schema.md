# F5 content-read evidence

Status: source-backed schema and read behavior. No production rows copied.

`upstream/Polaris-Emulator/Database/Default Database/CleanDB.sql:41439-41448` defines `hotelview_news` with `id`, `title`, `text`, `button_text`, `button_type` (`client` or `web`), `button_link`, and `image`. The lengths are 100, 500, 50, 200, and 200 characters as declared by the DDL.

`Emulator/src/main/java/com/eu/habbo/habbohotel/hotelview/NewsList.java:24-33` reads `SELECT * FROM hotelview_news ORDER BY id DESC LIMIT 10` and maps each row through `NewsWidget`. `NewsWidget.java:17-28` maps all seven columns; `client` becomes type `1` and every other schema-proven enum value (`web`) becomes type `0`.

The Go unit may expose only these seven fields and the same descending-ID, ten-row limit. It is read-only. Unknown or malformed enum values must return an error rather than be guessed. No content writes, asset retrieval, client handoff, or production route is included.
