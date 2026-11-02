-- Review/apply through the server-side migration role. Not applied by this repo.
-- No browser role receives schema access, policies or table privileges.
begin;
create schema game_private;
revoke all on schema game_private from public, anon, authenticated;
alter default privileges in schema game_private revoke all on tables from public, anon, authenticated;
alter default privileges in schema game_private revoke all on sequences from public, anon, authenticated;

create type game_private.mode as enum ('quote_completion', 'niche', 'hive_mind');
create table game_private.channels (
    id text primary key,
    owner_twitch_id text not null,
    -- No cooldown default: counting semantics and allowed values remain open.
    cooldown_completed_games integer check (cooldown_completed_games >= 0)
);
create table game_private.moderator_grants (
    channel_id text not null references game_private.channels(id),
    moderator_twitch_id text not null,
    permission text not null check (permission in ('question_review', 'live_control', 'settings')),
    granted_by text not null,
    primary key(channel_id, moderator_twitch_id, permission)
);
create function game_private.owner_only_grant() returns trigger language plpgsql as $$
begin
    if not exists (select 1 from game_private.channels where id = new.channel_id and owner_twitch_id = new.granted_by) then
        raise exception 'Only the channel owner may grant permissions';
    end if;
    return new;
end $$;
create trigger verify_grant_owner before insert or update on game_private.moderator_grants
    for each row execute function game_private.owner_only_grant();

create table game_private.bank_questions (
    channel_id text not null references game_private.channels(id),
    id uuid not null,
    mode game_private.mode not null,
    prompt text not null check (length(trim(prompt)) > 0),
    canonical_answer text,
    valid_words jsonb,
    source_reference jsonb,
    source_validated boolean not null default false,
    review_status text not null check (review_status in ('pending', 'approved', 'rejected')),
    origin text not null check (origin in ('viewer', 'moderator', 'ai')),
    created_by text not null,
    primary key(channel_id, id),
    check (mode <> 'quote_completion' or review_status <> 'approved' or
           (canonical_answer is not null and source_reference is not null and source_validated)),
    check (mode <> 'niche' or review_status <> 'approved' or
           (valid_words is not null and jsonb_typeof(valid_words) = 'array'))
);
create table game_private.games (
    channel_id text not null references game_private.channels(id),
    id uuid not null,
    phase text not null,
    state_version bigint not null check (state_version >= 0),
    current_round_position integer,
    current_question_position integer,
    policy_snapshot jsonb not null,
    created_at timestamptz not null default now(),
    completed_at timestamptz,
    primary key(channel_id, id)
);
create table game_private.rounds (
    channel_id text not null,
    game_id uuid not null,
    id uuid not null,
    position integer not null check (position > 0),
    mode game_private.mode not null,
    question_count integer not null check (question_count between 3 and 5),
    primary key(channel_id, id),
    unique(channel_id, game_id, position),
    unique(channel_id, game_id, id),
    foreign key(channel_id, game_id) references game_private.games(channel_id, id)
);
create table game_private.questions (
    channel_id text not null,
    game_id uuid not null,
    round_id uuid not null,
    id uuid not null,
    bank_question_id uuid not null,
    position integer not null check (position between 1 and 5),
    -- Immutable source/answer snapshot is private; expose only public DTOs.
    private_snapshot jsonb not null,
    phase text not null,
    deadline timestamptz,
    primary key(channel_id, id),
    unique(channel_id, game_id, id),
    unique(channel_id, round_id, position),
    unique(channel_id, game_id, bank_question_id),
    foreign key(channel_id, game_id, round_id) references game_private.rounds(channel_id, game_id, id),
    foreign key(channel_id, bank_question_id) references game_private.bank_questions(channel_id, id)
);
create table game_private.reservations (
    channel_id text not null,
    bank_question_id uuid not null,
    game_id uuid not null,
    primary key(channel_id, bank_question_id),
    foreign key(channel_id, bank_question_id) references game_private.bank_questions(channel_id, id),
    foreign key(channel_id, game_id) references game_private.games(channel_id, id)
);
create table game_private.question_usage (
    channel_id text not null,
    bank_question_id uuid not null,
    game_id uuid not null,
    used_at timestamptz not null,
    primary key(channel_id, bank_question_id, game_id),
    foreign key(channel_id, bank_question_id) references game_private.bank_questions(channel_id, id),
    foreign key(channel_id, game_id) references game_private.games(channel_id, id)
);
create table game_private.submissions (
    channel_id text not null,
    question_id uuid not null,
    viewer_twitch_id text not null,
    id uuid not null unique,
    answer text not null check (length(trim(answer)) > 0),
    received_at timestamptz not null default now(),
    primary key(channel_id, question_id, viewer_twitch_id),
    foreign key(channel_id, question_id) references game_private.questions(channel_id, id)
);
create function game_private.reject_submission_change() returns trigger language plpgsql as $$
begin
    raise exception 'Accepted submissions are immutable';
end $$;
create trigger immutable_submission before update on game_private.submissions
    for each row execute function game_private.reject_submission_change();

-- RLS defense in depth; no client policies. Use a dedicated server DB role.
alter table game_private.channels enable row level security;
alter table game_private.moderator_grants enable row level security;
alter table game_private.bank_questions enable row level security;
alter table game_private.games enable row level security;
alter table game_private.rounds enable row level security;
alter table game_private.questions enable row level security;
alter table game_private.reservations enable row level security;
alter table game_private.question_usage enable row level security;
alter table game_private.submissions enable row level security;
revoke all on all tables in schema game_private from public, anon, authenticated;
revoke all on all functions in schema game_private from public, anon, authenticated;
commit;
