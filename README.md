# RankMePlis (Python-Flask based CSGO Lobby Website)

DataBase
CREATE TABLE `api` ( `id` INTEGER NOT NULL, `ip` VARCHAR(15), `api_key` VARCHAR(64), `write` VARCHAR(5), PRIMARY KEY(`id`) )
CREATE TABLE "lobby" ( `id` INTEGER NOT NULL, `lobby_id` VARCHAR(40), `timestamp` INTEGER NOT NULL, `type` VARCHAR(40), `min_rank` INTEGER, `prime` VARCHAR(5), `external` VARCHAR(5), PRIMARY KEY(`id`) )
CREATE TABLE "user" ( `id` INTEGER NOT NULL, `steam_id` VARCHAR(40), `nickname` VARCHAR(80), `lobby_id` VARCHAR(40), `avatar_url` VARCHAR(150), PRIMARY KEY(`id`) )