--select *
----	event_key,event_date,event_time,event_first_player,first_player_key,event_second_player,second_player_key
--	--,event_final_result,event_game_result,event_serve,event_winner,event_status,
----	event_type_type,
----	tournament_name
--	--tournament_key,tournament_round,tournament_season,download_time
--from tenis_api.fixtures_for_today
--order by event_first_player
--event_second_player limit 10;


/*
 * falta agrregar filtros de singles o torneos en todo caso (exhibition dejar fuera, etc)   PRINCIPALMENTE EN PASO ANTERIOR
 * 
 * filtrar tmb partidos cancelados y alguna otra cosa rara???
 * 
 * aca ver si quedan aun muchos nulos luego de aplicar filtros, en todo cso ver q hacer con nulos, pasar a 0 o q
 * 
 * add ODDS!! para cual, todos y duplico linea por cada uno??
 * 
 *  * correjido:
 * - event_type_2, se arreglo la query para generar lal col, estaban quedndo valores extra ya q qeudbabn espacios en blanco o linas q ahcianq parecieran difefrentes categorias
 * 
 * */

begin;

drop table if exists odds_pivoted_temp;
create temp table odds_pivoted_temp as
with odds_pivoted as (
	select
	    event_key,
	    max(case when betting_house='10Bet' then home_odds else null end) as "10bet_hm_odds",
	    max(case when betting_house='10Bet' then away_odds else null end) as "10bet_aw_odds",
	    max(case when betting_house='188bet' then home_odds else null end) as "188bet_hm_odds",
	    max(case when betting_house='188bet' then away_odds else null end) as "188bet_aw_odds",
	    max(case when betting_house='1xBet' then home_odds else null end) as "1xbet_hm_odds",
	    max(case when betting_house='1xBet' then away_odds else null end) as "1xbet_aw_odds",
	    max(case when betting_house='888Sport' then home_odds else null end) as "888sport_hm_odds",
	    max(case when betting_house='888Sport' then away_odds else null end) as "888sport_aw_odds",
	    max(case when betting_house='bet365' then home_odds else null end) as "bet365_hm_odds",
	    max(case when betting_house='bet365' then away_odds else null end) as "bet365_aw_odds",
	    max(case when betting_house='Betano' then home_odds else null end) as "betano_hm_odds",
	    max(case when betting_house='Betano' then away_odds else null end) as "betano_aw_odds",
	    max(case when betting_house='Betfair' then home_odds else null end) as "betfair_hm_odds",
	    max(case when betting_house='Betfair' then away_odds else null end) as "betfair_aw_odds",
	    max(case when betting_house='Marathon' then home_odds else null end) as "marathon_hm_odds",
	    max(case when betting_house='Marathon' then away_odds else null end) as "marathon_aw_odds",
	    max(case when betting_house='Pncl' then home_odds else null end) as "pncl_hm_odds",
	    max(case when betting_house='Pncl' then away_odds else null end) as "pncl_aw_odds",
	    max(case when betting_house='Sbo' then home_odds else null end) as "sbo_hm_odds",
	    max(case when betting_house='Sbo' then away_odds else null end) as "sbo_aw_odds",
	    max(case when betting_house='Superbet' then home_odds else null end) as "superbet_hm_odds",
	    max(case when betting_house='Superbet' then away_odds else null end) as "superbet_aw_odds",
	    max(case when betting_house='Unibet' then home_odds else null end) as "unibet_hm_odds",
	    max(case when betting_house='Unibet' then away_odds else null end) as "unibet_aw_odds",
	    max(case when betting_house='WilliamHill' then home_odds else null end) as "williamhill_hm_odds",
	    max(case when betting_house='WilliamHill' then away_odds else null end) as "williamhill_aw_odds"
	from tenis_api.odds_for_today
	group by 1
)
select
    *,
    coalesce(
	    "bet365_hm_odds",
	    round(
	        (coalesce("10bet_hm_odds", 0) + coalesce("188bet_hm_odds", 0) + coalesce("1xbet_hm_odds", 0) + coalesce("888sport_hm_odds", 0)
	        + coalesce("betano_hm_odds", 0) + coalesce("betfair_hm_odds", 0) + coalesce("marathon_hm_odds", 0)
	        + coalesce("pncl_hm_odds", 0) + coalesce("sbo_hm_odds", 0) + coalesce("superbet_hm_odds", 0) + coalesce("unibet_hm_odds", 0)
	        + coalesce("williamhill_hm_odds", 0))
	        / nullif(
	            (case when "10bet_hm_odds"      is not null then 1 else 0 end +
	             case when "188bet_hm_odds"      is not null then 1 else 0 end +
	             case when "1xbet_hm_odds"       is not null then 1 else 0 end +
	             case when "888sport_hm_odds"    is not null then 1 else 0 end +
	             case when "betano_hm_odds"      is not null then 1 else 0 end +
	             case when "betfair_hm_odds"     is not null then 1 else 0 end +
	             case when "marathon_hm_odds"    is not null then 1 else 0 end +
	             case when "pncl_hm_odds"        is not null then 1 else 0 end +
	             case when "sbo_hm_odds"         is not null then 1 else 0 end +
	             case when "superbet_hm_odds"    is not null then 1 else 0 end +
	             case when "unibet_hm_odds"      is not null then 1 else 0 end +
	             case when "williamhill_hm_odds" is not null then 1 else 0 end),
	        0),
	    2)
	) as home_odds,
    coalesce(
	    "bet365_aw_odds",
	    round(
	        (coalesce("10bet_aw_odds", 0) + coalesce("188bet_aw_odds", 0) + coalesce("1xbet_aw_odds", 0) + coalesce("888sport_aw_odds", 0)
	        + coalesce("betano_aw_odds", 0) + coalesce("betfair_aw_odds", 0) + coalesce("marathon_aw_odds", 0)
	        + coalesce("pncl_aw_odds", 0) + coalesce("sbo_aw_odds", 0) + coalesce("superbet_aw_odds", 0) + coalesce("unibet_aw_odds", 0)
	        + coalesce("williamhill_aw_odds", 0))
	        / nullif(
	            (case when "10bet_aw_odds"       is not null then 1 else 0 end +
	             case when "188bet_aw_odds"      is not null then 1 else 0 end +
	             case when "1xbet_aw_odds"       is not null then 1 else 0 end +
	             case when "888sport_aw_odds"    is not null then 1 else 0 end +
	             case when "betano_aw_odds"      is not null then 1 else 0 end +
	             case when "betfair_aw_odds"     is not null then 1 else 0 end +
	             case when "marathon_aw_odds"    is not null then 1 else 0 end +
	             case when "pncl_aw_odds"        is not null then 1 else 0 end +
	             case when "sbo_aw_odds"         is not null then 1 else 0 end +
	             case when "superbet_aw_odds"    is not null then 1 else 0 end +
	             case when "unibet_aw_odds"      is not null then 1 else 0 end +
	             case when "williamhill_aw_odds" is not null then 1 else 0 end),
	        0),
	    2)
	) as away_odds
from odds_pivoted;


--- query
--drop table if exists tenis_api.main_todays_games_details;
--create table tenis_api.main_todays_games_details as
delete from tenis_api.main_todays_games_details;
insert into tenis_api.main_todays_games_details
with fixture_data as (
	select
		event_key,event_date,event_time,event_first_player,
		first_player_key,event_second_player,second_player_key,
		coalesce(event_first_player_logo, 'https://wgdbjjhhmftlunxdmltb.supabase.co/storage/v1/object/public/tenis-api-streamlite-test/player_default.jpg') as event_first_player_logo,
		coalesce(event_second_player_logo, 'https://wgdbjjhhmftlunxdmltb.supabase.co/storage/v1/object/public/tenis-api-streamlite-test/player_default.jpg') as event_second_player_logo,
		case 
			when event_status IN ('Finished', 'Retired', 'Awarded', 'Walk Over') then 'Finished'
			when event_status like 'Set%' then 'In progress'
			when event_status='Cancelled' then event_status
			when event_status='Interrupted' then event_status
			else 'Not yet started'
		end as event_status,
		case 
			when event_winner='First Player' then 'P1'
			when event_winner='Second Player' then 'P2'
			else event_winner
		end as event_winner,
		a.tournament_name,
		case 
			when a.event_type_type like '%Singles%' then 'Singles'
			when a.event_type_type like '%Doubles%' then 'Doubles'
			else 'unkn'
		end as event_type,
		trim(replace(replace(replace(a.event_type_type, ' Singles',''),' Doubles',''),'-','')) as event_type_2,
		trim(replace(replace(replace(replace(replace(a.event_type_type, ' Singles',''),' Doubles',''),'-',''),'Men',''),'Women','')) as event_type_3,
		a.event_type_type,
		case 
			when a.event_type_type like '%Men%' or a.event_type_type like '%Atp%' then 'Men'
			when a.event_type_type like '%Women%' or a.event_type_type like '%Wta%' then 'Women'
			else 'unkn'
		end as event_gender,		
--		t.tournament_sourface
		coalesce(nullif(initcap(replace(tournament_sourface, ' (Indoor)', '')),''),'unkn') as tournament_sourface --- taken care of removing ' (Indoor)' and converting 'clay'/'hard' to capital case ***also in query 1
	from tenis_api.fixtures_for_today a
	left join tenis_api.tournaments t
	on a.tournament_key=t.tournament_key
	),
add_players_info as (
	select
		fd.*,
		p1s.wins_sourface as p1_wins_sourface,
		p1s.losses_sourface as p1_losses_sourface,
		p2s.wins_sourface as p2_wins_sourface,
		p2s.losses_sourface as p2_losses_sourface,
		p1a.wins_all as p1_wins_all,
		p1a.losses_all as p1_losses_all,
		p2a.wins_all as p2_wins_all,
		p2a.losses_all as p2_losses_all,
		coalesce(sp1.points, '0') as p1_points,
		coalesce(sp2.points, '0') as p2_points
	from fixture_data fd
	left join tenis_api.stg_players_results_by_sourface p1s
		on fd.first_player_key=p1s.player_id
		and fd.tournament_sourface=p1s.tournament_sourface
	left join tenis_api.stg_players_results_by_sourface p2s
		on fd.second_player_key=p2s.player_id
		and fd.tournament_sourface=p2s.tournament_sourface
	left join tenis_api.stg_players_results_all p1a
		on fd.first_player_key=p1a.player_id
	left join tenis_api.stg_players_results_all p2a
		on fd.second_player_key=p2a.player_id
	left join tenis_api.standings sp1
		on fd.first_player_key=sp1.player_key
	left join tenis_api.standings sp2
		on fd.second_player_key=sp2.player_key
),
full_rendim as (
	select
		event_key,
		event_date,
		event_time,
		event_status,
		event_winner,
		event_first_player,first_player_key,
		event_second_player,second_player_key,
		tournament_sourface,
		tournament_name,
		event_type,
		event_type_2,
		event_type_3,
		event_type_type,
		event_gender,
		----- PLAYER 1
		p1_wins_sourface,p1_losses_sourface,
		p1_wins_all,p1_losses_all,
		coalesce(round(p1_wins_all::numeric / nullif((p1_wins_all+p1_losses_all),0), 3), 0) as p1_rend_all,
		coalesce(round(p1_wins_sourface::numeric / nullif((p1_wins_sourface+p1_losses_sourface),0), 3), 0) as p1_rend_sup,
		p1_points,
		event_first_player_logo,
		----- PLAYER 2
		p2_wins_sourface,p2_losses_sourface,
		p2_wins_all,p2_losses_all,
		coalesce(round(p2_wins_all::numeric / nullif((p2_wins_all+p2_losses_all),0), 3), 0) as p2_rend_all,
		coalesce(round(p2_wins_sourface::numeric / nullif((p2_wins_sourface+p2_losses_sourface),0), 3), 0) as p2_rend_sup,
		p2_points,
		event_second_player_logo
	from add_players_info
)
select
	f.*,
	coalesce(h.total_first_player_key, 0) as p1_wins_h2h,
	coalesce(h.p1_perc_h2h, 0) as p1_perc_h2h,
	coalesce(h.total_second_player_key, 0) as p2_wins_h2h,
	coalesce(h.p2_perc_h2h, 0) as p2_perc_h2h,
	o.home_odds as p1_odds,
	o.away_odds as p2_odds,
	current_timestamp as load_timestamp
from full_rendim f
left join tenis_api.stg_h2h_for_today_processed h
	on f.first_player_key=h.first_player_key and f.second_player_key=h.second_player_key
left join odds_pivoted_temp o -- TEMP TABLE NOW
		on f.event_key=o.event_key;

commit;

--select * from tenis_api.main_todays_games_details;	
--select count(*) from tenis_api.main_todays_games_details;

--select distinct event_gender from tenis_api.main_todays_games_details;


-- check
--select * from tenis_api.fixtures_results
--where first_player_key='95473' or second_player_key='95473';

-- USED TABLES
--select * from tenis_api.fixtures_for_today limit 10;
--select * from tenis_api.tournaments limit 10;
--select * from tenis_api.standings limit 10;
--
--select * from tenis_api.stg_players_results_by_sourface limit 10; -- created before
--select * from tenis_api.stg_players_results_all limit 10; -- created before
