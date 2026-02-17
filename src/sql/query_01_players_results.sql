/*
 * Query to get the player results information in general and by soruface
 *
 * First it gets the games for each player in the last year from fixtures_results table. Here the idea is to only use the unique players involded in the ixrute for the next days
 * Then it creates atable specific to sourfcace and another to general results
 * 
 * */

drop table if exists player_results_tmp;
create temp table player_results_tmp as
with all_player_ids as (
    select distinct player_id
    from (
        select first_player_key as player_id from tenis_api.fixtures_for_today
--        	where event_status IN ('Finished', 'Retired', 'Awarded', 'Walk Over') -- getting only data from table with a single event date
        union
        select second_player_key as player_id from tenis_api.fixtures_for_today
--        	where event_status IN ('Finished', 'Retired', 'Awarded', 'Walk Over') -- getting only data from table with a single event date
		-- union
		-- select '2382' as player_id -- testing
    ) a
),
no_dups as (
	select * from (
		select *, row_number() over (partition by event_key order by download_time) as rn
		from tenis_api.fixtures_results
		where (first_player_key in (select player_id from all_player_ids)
			or second_player_key in (select player_id from all_player_ids))
			and event_date::date between current_date-365 and current_date -- for yearly ---- ver si meto fecha especifica (aunque si es carga diaria no iria, solo en manual)
--			and event_type_type='Atp Singles'
			and event_status IN ('Finished', 'Retired', 'Awarded', 'Walk Over') --- aadding here, not above since i need all players where game is not finished mainly (games for today)
		) a
	where rn=1
-- 	and first_player_key='2382'
) -- select * from no_dups;
, -- select * from all_player_ids;
player_results as (
    select 
        p.player_id,
        f.*,
        case 
            when f.first_player_key = p.player_id then 'first'
            when f.second_player_key = p.player_id then 'second'
        end as player_position,
        case
            when event_winner = 'First Player' then first_player_key
            when event_winner = 'Second Player' then second_player_key
            else null
        end as winner_key
    from all_player_ids p
    join no_dups f 
        on (f.first_player_key = p.player_id or f.second_player_key = p.player_id)
    where f.event_status IN ('Finished', 'Retired')
)
select * from player_results
--where player_id=1961
;



drop table if exists tenis_api.stg_players_results_by_sourface;
create table tenis_api.stg_players_results_by_sourface as
select
    current_date as run_date,
    player_id,
	coalesce(nullif(initcap(replace(tournament_sourface, ' (Indoor)', '')),''),'unkn') as tournament_sourface, --- taken care of removing ' (Indoor)' and converting 'clay'/'hard' to capital case ***also in query 2
    count(*) as total_games_sourface,
    sum(case when winner_key = player_id then 1 else 0 end) as wins_sourface,
    sum(case when winner_key is not null and winner_key != player_id then 1 else 0 end) as losses_sourface,
    sum(case when winner_key is null then 1 else 0 end) as draws_or_other_sourface
from player_results_tmp a
left join tenis_api.tournaments t
on a.tournament_key=t.tournament_key
group by 1,2,3;


drop table if exists tenis_api.stg_players_results_all;
create table tenis_api.stg_players_results_all as
select
    current_date as run_date,
    player_id,
    count(*) as total_games_all,
    sum(case when winner_key = player_id then 1 else 0 end) as wins_all,
    sum(case when winner_key is not null and winner_key != player_id then 1 else 0 end) as losses_all,
    sum(case when winner_key is null then 1 else 0 end) as draws_or_other_all
from player_results_tmp a
group by 1,2;

--select initcap('Hard');

--select * from tenis_api.stg_players_results_by_sourface order by 2;
--select * from tenis_api.stg_players_results_all order by 2;

-- USED TABLES
--select * from tenis_api.fixtures_for_today limit 10;
--select * from tenis_api.fixtures_results limit 10;
--select * from tenis_api.tournaments limit 10;

-- checks
--select * from tenis_api.fixtures_results where download_time=(select max(download_time) from tenis_api.fixtures_results) limit 10;
--select distinct event_date from tenis_api.fixtures_for_today;
--select count(*) from tenis_api.fixtures_for_today;

-- check sorufaces to fix names
--select distinct tournament_sourface from tenis_api.tournaments;
--select tournament_sourface, count(*)
--from tenis_api.tournaments
--group by 1 order by 2 desc;
--select tournament_sourface, tournament_name, event_type_type
--from tenis_api.tournaments
--where tournament_sourface not in ('Hard', 'Clay', 'Hard (Indoor)', 'Grass', 'Clay (Indoor)')
--order by 1, 2;



