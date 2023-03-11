CREATE TABLE IF NOT EXISTS guilds(guildId BIGINT PRIMARY KEY,
                                 data STRING);


CREATE TABLE IF NOT EXISTS users(userId BIGINT PRIMARY KEY,
                                 data STRING);


CREATE TABLE IF NOT EXISTS rssFeedLastPosted(channelfeed STRING PRIMARY KEY,
                                 data STRING);

CREATE TABLE IF NOT EXISTS buttonRoles(data STRING);

CREATE TABLE IF NOT EXISTS movieSuggestions (data TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS rssFeeds (data TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS recurringReminders (data TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS highlights (
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    phrase TEXT NOT NULL,
    snooze_until INT,
    PRIMARY KEY (guild_id, user_id, phrase)
)
