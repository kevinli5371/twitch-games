CREATE TABLE twitch_games.channels (
    id varchar(32) PRIMARY KEY CHECK (id ~ '^[1-9][0-9]*$'),
    display_name text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE twitch_games.participants (
    id varchar(32) PRIMARY KEY CHECK (id ~ '^[1-9][0-9]*$'),
    display_name text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE twitch_games.streams (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id varchar(32) NOT NULL REFERENCES twitch_games.channels(id),
    twitch_stream_id varchar(128) NOT NULL,
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (channel_id, twitch_stream_id),
    UNIQUE (id, channel_id),
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE twitch_games.transcript_batches (
    id uuid PRIMARY KEY,
    stream_id uuid NOT NULL,
    channel_id varchar(32) NOT NULL,
    source text NOT NULL,
    payload_digest varchar(64) NOT NULL CHECK (payload_digest ~ '^[0-9a-f]{64}$'),
    received_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, stream_id, channel_id),
    FOREIGN KEY (stream_id, channel_id) REFERENCES twitch_games.streams(id, channel_id)
);

CREATE TABLE twitch_games.transcript_segments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id uuid NOT NULL,
    stream_id uuid NOT NULL,
    channel_id varchar(32) NOT NULL,
    sequence bigint NOT NULL CHECK (sequence >= 0),
    text text NOT NULL CHECK (length(btrim(text)) > 0 AND length(text) <= 4000),
    observed_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (batch_id, sequence),
    UNIQUE (id, stream_id, channel_id),
    FOREIGN KEY (batch_id, stream_id, channel_id)
        REFERENCES twitch_games.transcript_batches(id, stream_id, channel_id)
);
CREATE INDEX transcript_stream_order ON twitch_games.transcript_segments
    (channel_id, stream_id, received_at, id);

CREATE TABLE twitch_games.question_candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    stream_id uuid NOT NULL,
    channel_id varchar(32) NOT NULL,
    complete_quote text NOT NULL CHECK (length(complete_quote) BETWEEN 1 AND 4000),
    prompt text NOT NULL CHECK (length(prompt) > 0),
    canonical_answer text NOT NULL CHECK (length(btrim(canonical_answer)) BETWEEN 1 AND 256),
    quote_digest varchar(64) NOT NULL CHECK (quote_digest ~ '^[0-9a-f]{64}$'),
    blank_start integer NOT NULL CHECK (blank_start >= 0),
    blank_end integer NOT NULL CHECK (blank_end > blank_start),
    accepted_aliases jsonb NOT NULL CHECK (jsonb_typeof(accepted_aliases) = 'array'),
    review_status text NOT NULL CHECK (review_status IN ('pending', 'approved', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, stream_id, channel_id),
    UNIQUE (stream_id, quote_digest, blank_start, blank_end),
    FOREIGN KEY (stream_id, channel_id) REFERENCES twitch_games.streams(id, channel_id),
    CHECK (blank_end <= length(complete_quote)),
    CHECK (substring(complete_quote FROM blank_start + 1 FOR blank_end - blank_start)
        = canonical_answer),
    CHECK (overlay(complete_quote PLACING '____' FROM blank_start + 1
        FOR blank_end - blank_start) = prompt)
);
CREATE INDEX candidate_queue ON twitch_games.question_candidates
    (channel_id, stream_id, review_status, created_at);

CREATE TABLE twitch_games.question_sources (
    question_id uuid NOT NULL,
    segment_id uuid NOT NULL,
    stream_id uuid NOT NULL,
    channel_id varchar(32) NOT NULL,
    PRIMARY KEY (question_id, segment_id),
    FOREIGN KEY (question_id, stream_id, channel_id)
        REFERENCES twitch_games.question_candidates(id, stream_id, channel_id),
    FOREIGN KEY (segment_id, stream_id, channel_id)
        REFERENCES twitch_games.transcript_segments(id, stream_id, channel_id)
);

CREATE TABLE twitch_games.game_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    stream_id uuid NOT NULL,
    channel_id varchar(32) NOT NULL,
    mode text NOT NULL CHECK (mode = 'quote'),
    status text NOT NULL CHECK (status IN ('inactive', 'active', 'ended')),
    policy_id varchar(128) NOT NULL CHECK (length(btrim(policy_id)) > 0),
    policy_snapshot jsonb NOT NULL CHECK (jsonb_typeof(policy_snapshot) = 'object'),
    version bigint NOT NULL CHECK (version >= 0),
    started_at timestamptz,
    ended_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, stream_id, channel_id),
    FOREIGN KEY (stream_id, channel_id) REFERENCES twitch_games.streams(id, channel_id),
    CHECK (ended_at IS NULL OR (started_at IS NOT NULL AND ended_at >= started_at))
);
CREATE UNIQUE INDEX one_active_game_per_channel ON twitch_games.game_sessions(channel_id)
    WHERE status = 'active';

CREATE TABLE twitch_games.rounds (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id uuid NOT NULL,
    stream_id uuid NOT NULL,
    channel_id varchar(32) NOT NULL,
    question_id uuid NOT NULL,
    phase text NOT NULL CHECK (phase IN
        ('prepared', 'answering', 'closed', 'scoring', 'results', 'cancelled')),
    version bigint NOT NULL CHECK (version >= 0),
    prompt_snapshot text NOT NULL CHECK (length(prompt_snapshot) > 0),
    canonical_answer_snapshot text NOT NULL
        CHECK (length(btrim(canonical_answer_snapshot)) BETWEEN 1 AND 256),
    accepted_aliases_snapshot jsonb NOT NULL
        CHECK (jsonb_typeof(accepted_aliases_snapshot) = 'array'),
    scoring_policy_id varchar(128) NOT NULL CHECK (length(btrim(scoring_policy_id)) > 0),
    policy_snapshot jsonb NOT NULL CHECK (jsonb_typeof(policy_snapshot) = 'object'),
    opened_at timestamptz,
    closes_at timestamptz,
    closed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, game_id, channel_id),
    UNIQUE (id, game_id, channel_id, scoring_policy_id),
    FOREIGN KEY (game_id, stream_id, channel_id)
        REFERENCES twitch_games.game_sessions(id, stream_id, channel_id),
    FOREIGN KEY (question_id, stream_id, channel_id)
        REFERENCES twitch_games.question_candidates(id, stream_id, channel_id),
    CHECK (closes_at IS NULL OR (opened_at IS NOT NULL AND closes_at >= opened_at)),
    CHECK (closed_at IS NULL OR (opened_at IS NOT NULL AND closed_at >= opened_at))
);
CREATE UNIQUE INDEX one_open_round_per_game ON twitch_games.rounds(game_id)
    WHERE phase IN ('prepared', 'answering', 'closed', 'scoring');

CREATE TABLE twitch_games.submissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    round_id uuid NOT NULL,
    game_id uuid NOT NULL,
    channel_id varchar(32) NOT NULL,
    participant_id varchar(32) NOT NULL REFERENCES twitch_games.participants(id),
    request_id uuid NOT NULL,
    raw_answer text NOT NULL CHECK (length(raw_answer) BETWEEN 1 AND 256
        AND raw_answer ~ '[^[:space:]]' AND raw_answer !~ '[[:cntrl:]]'),
    received_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (round_id, participant_id, request_id),
    UNIQUE (id, round_id, game_id, channel_id, participant_id),
    FOREIGN KEY (round_id, game_id, channel_id)
        REFERENCES twitch_games.rounds(id, game_id, channel_id)
);
CREATE INDEX submissions_for_round ON twitch_games.submissions(round_id, received_at);

CREATE TABLE twitch_games.score_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id uuid NOT NULL UNIQUE,
    round_id uuid NOT NULL,
    game_id uuid NOT NULL,
    channel_id varchar(32) NOT NULL,
    participant_id varchar(32) NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('correct', 'incorrect')),
    points integer NOT NULL,
    scoring_policy_id varchar(128) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (round_id, participant_id),
    FOREIGN KEY (submission_id, round_id, game_id, channel_id, participant_id)
        REFERENCES twitch_games.submissions(id, round_id, game_id, channel_id, participant_id),
    FOREIGN KEY (round_id, game_id, channel_id, scoring_policy_id)
        REFERENCES twitch_games.rounds(id, game_id, channel_id, scoring_policy_id)
);
CREATE INDEX leaderboard_totals ON twitch_games.score_entries
    (channel_id, game_id, participant_id) INCLUDE (points);

-- All business tables live outside public and deny direct client access.
DO $$
DECLARE table_name text; role_name text;
BEGIN
    FOR table_name IN SELECT tablename FROM pg_tables WHERE schemaname = 'twitch_games'
        AND tablename <> 'alembic_version'
    LOOP
        EXECUTE format('ALTER TABLE twitch_games.%I ENABLE ROW LEVEL SECURITY', table_name);
    END LOOP;
    REVOKE ALL ON ALL TABLES IN SCHEMA twitch_games FROM PUBLIC;
    ALTER DEFAULT PRIVILEGES IN SCHEMA twitch_games REVOKE ALL ON TABLES FROM PUBLIC;
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON SCHEMA twitch_games FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA twitch_games FROM %I', role_name);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA twitch_games '
                'REVOKE ALL ON TABLES FROM %I', role_name);
        END IF;
    END LOOP;
END $$;
