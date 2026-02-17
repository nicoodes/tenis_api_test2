--- query
drop table if exists tenis_api.stg_h2h_for_today_processed;
create table tenis_api.stg_h2h_for_today_processed as
with base_data_h2h as (
	select
        event_key,event_date,event_first_player,first_player_key,event_second_player,second_player_key,
        event_final_result,event_winner,
		first_player_key as p1,
		case 
			when event_winner='First Player' then 1 else 0
		end as p1_win,
		second_player_key as p2,
		case 
			when event_winner='Second Player' then 1 else 0
		end as p2_win
	from tenis_api.h2h_for_today2
	),
right_players as (
	select *,
		case 
			when p1 < p2 then p1 else p2
		end as p1_final,
		case 
			when p1 < p2 then p1_win else p2_win
		end as p1_win_final,
		case 
			when p1 > p2 then p1 else p2
		end as p2_final,
		case 
			when p1 > p2 then p1_win else p2_win
		end as p2_win_final
	from base_data_h2h
	) --select * from right_players;
, grouped_h2h as (
	select
	    p1_final as first_player_key, sum(p1_win_final) as total_first_player_key,
	    p2_final as second_player_key, sum(p2_win_final) as total_second_player_key
	from right_players group by p1_final, p2_final
	union all
	select
	    p2_final as first_player_key, sum(p2_win_final) as total_first_player_key,
	    p1_final as second_player_key, sum(p1_win_final) as total_second_player_key
	from right_players group by p2_final, p1_final
)
select
	*,
	round(total_first_player_key::numeric / nullif((total_first_player_key+total_second_player_key),0),4) as p1_perc_h2h,
	round(total_second_player_key::numeric/ nullif((total_first_player_key+total_second_player_key),0),4) as p2_perc_h2h
from grouped_h2h;



--select * from tenis_api.stg_h2h_for_today_processed order by 1;


