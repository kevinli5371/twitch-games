CREATE TABLE twitch_games.twitch_users (
    id varchar(32) PRIMARY KEY CHECK (id ~ '^[1-9][0-9]*$'),
    login text,
    display_name text,
    profile_image_url text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO twitch_games.twitch_users(id,display_name)
    SELECT id,display_name FROM twitch_games.channels;
ALTER TABLE twitch_games.channels ADD COLUMN owner_twitch_id varchar(32)
    GENERATED ALWAYS AS (id) STORED;
CREATE TABLE twitch_games.oauth_authorizations (
    user_id varchar(32) PRIMARY KEY REFERENCES twitch_games.twitch_users(id),
    encrypted_access_token text NOT NULL,
    encrypted_refresh_token text,
    access_expires_at timestamptz NOT NULL,
    validated_at timestamptz NOT NULL,
    revoked_at timestamptz
);
INSERT INTO twitch_games.oauth_authorizations
    (user_id,encrypted_access_token,access_expires_at,validated_at)
    SELECT DISTINCT ON(channel_id) channel_id,encrypted_token,expires_at,validated_at
    FROM twitch_games.dashboard_sessions ORDER BY channel_id,validated_at DESC;
ALTER TABLE twitch_games.dashboard_sessions ADD COLUMN user_id varchar(32)
    REFERENCES twitch_games.oauth_authorizations(user_id);
UPDATE twitch_games.dashboard_sessions SET user_id=channel_id;
ALTER TABLE twitch_games.dashboard_sessions ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE twitch_games.dashboard_sessions DROP COLUMN channel_id,
    DROP COLUMN encrypted_token, DROP COLUMN validated_at;
CREATE INDEX dashboard_session_by_user ON twitch_games.dashboard_sessions(user_id);
CREATE INDEX authorization_due ON twitch_games.oauth_authorizations(validated_at)
    WHERE revoked_at IS NULL;
CREATE TABLE twitch_games.moderator_grants (
    channel_id varchar(32) NOT NULL REFERENCES twitch_games.channels(id),
    moderator_twitch_id varchar(32) NOT NULL REFERENCES twitch_games.twitch_users(id),
    permission text NOT NULL CHECK (permission IN ('question_review','live_control','settings')),
    granted_by varchar(32) NOT NULL REFERENCES twitch_games.twitch_users(id),
    granted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (channel_id,moderator_twitch_id,permission),
    CHECK (granted_by=channel_id AND moderator_twitch_id<>channel_id)
);
CREATE INDEX grants_for_user ON twitch_games.moderator_grants(moderator_twitch_id,channel_id);
DO $$ DECLARE table_name text; role_name text; BEGIN
    FOREACH table_name IN ARRAY ARRAY['twitch_users','oauth_authorizations','moderator_grants'] LOOP
        EXECUTE format('ALTER TABLE twitch_games.%I ENABLE ROW LEVEL SECURITY',table_name);
    END LOOP;
    REVOKE ALL ON ALL TABLES IN SCHEMA twitch_games FROM PUBLIC;
    FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA twitch_games FROM %I',role_name);
            EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA twitch_games FROM %I',role_name);
        END IF;
    END LOOP;
END $$;
