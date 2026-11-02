ALTER TABLE twitch_games.channels ADD COLUMN version bigint NOT NULL DEFAULT 0 CHECK (version >= 0);
ALTER TABLE twitch_games.submissions ADD COLUMN revision bigint GENERATED ALWAYS AS IDENTITY;
CREATE INDEX submission_latest ON twitch_games.submissions (round_id, participant_id, revision DESC);
ALTER TABLE twitch_games.question_candidates ADD COLUMN generator_version text NOT NULL DEFAULT 'legacy';
CREATE TABLE twitch_games.oauth_states (
    digest char(64) PRIMARY KEY,
    expires_at timestamptz NOT NULL
);
CREATE TABLE twitch_games.dashboard_sessions (
    digest char(64) PRIMARY KEY,
    channel_id varchar(32) NOT NULL REFERENCES twitch_games.channels(id),
    encrypted_token text NOT NULL,
    expires_at timestamptz NOT NULL,
    validated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX session_validation ON twitch_games.dashboard_sessions(validated_at);
CREATE TABLE twitch_games.answer_aliases (
    channel_id varchar(32) NOT NULL REFERENCES twitch_games.channels(id),
    canonical text NOT NULL CHECK (length(canonical) BETWEEN 1 AND 256),
    aliases jsonb NOT NULL CHECK (jsonb_typeof(aliases)='array'),
    PRIMARY KEY (channel_id, canonical)
);
CREATE TABLE twitch_games.command_receipts (
    channel_id varchar(32) NOT NULL REFERENCES twitch_games.channels(id),
    request_id uuid NOT NULL,
    digest char(64) NOT NULL,
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (channel_id,request_id)
);
CREATE TABLE twitch_games.state_notifications (
    channel_id varchar(32) PRIMARY KEY REFERENCES twitch_games.channels(id),
    version bigint NOT NULL,
    published_version bigint NOT NULL DEFAULT -1,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    attempts integer NOT NULL DEFAULT 0,
    last_sent_at timestamptz
);
DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['oauth_states','dashboard_sessions','answer_aliases',
        'command_receipts','state_notifications'] LOOP
        EXECUTE format('ALTER TABLE twitch_games.%I ENABLE ROW LEVEL SECURITY', table_name);
    END LOOP;
    REVOKE ALL ON ALL TABLES IN SCHEMA twitch_games FROM PUBLIC;
    REVOKE ALL ON ALL SEQUENCES IN SCHEMA twitch_games FROM PUBLIC;
END $$;
