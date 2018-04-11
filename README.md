# RankMePlis (Python-Flask based CSGO Lobby Website)

Features
 - Submit lobbies being connected via steam openid, duplicated are updated(no spam).
 - List submited lobbies on main page.
 - API:
   - Creation of APIKEY's, generated ones will be sticked to a certain IP on first use.
   - Addition of APIKEY's, will check if exist.
   - Addition of lobbies, internal or external lobbies.
   - Can obtain lobbies.
   - Can obtain last update timestamp.


DataBase
```
CREATE TABLE `api` ( `id` INTEGER NOT NULL, `ip` VARCHAR(15), `api_key` VARCHAR(64), `write` VARCHAR(5), PRIMARY KEY(`id`) )
CREATE TABLE "lobby" ( `id` INTEGER NOT NULL, `lobby_id` VARCHAR(40), `timestamp` INTEGER NOT NULL, `type` VARCHAR(40), `min_rank` INTEGER, `prime` VARCHAR(5), `external` VARCHAR(5), PRIMARY KEY(`id`) )
CREATE TABLE "user" ( `id` INTEGER NOT NULL, `steam_id` VARCHAR(40), `nickname` VARCHAR(80), `lobby_id` VARCHAR(40), `avatar_url` VARCHAR(150), PRIMARY KEY(`id`) )
```
No support granted, this software is provided as is.
