--- query 05
-- insert full analysis into historical analysis table


----- CREATE INITIAL
-- refresh materialized view tenis_api.main_todays_analysis;
-- drop table tenis_api.full_analysis_hist;
-- create table tenis_api.full_analysis_hist as
-- select * from tenis_api.main_todays_analysis
-- where jugador_a_apostar_cons<>'Sin apuesta' or jugador_a_apostar_vb<>'Sin apuesta';

-- select * from tenis_api.full_analysis_hist;



----- DAILY INSERT
begin;

refresh materialized view tenis_api.main_todays_analysis;

delete from tenis_api.full_analysis_hist
where event_date in (
  select event_date from tenis_api.main_todays_analysis
  where jugador_a_apostar_cons<>'Sin apuesta' or jugador_a_apostar_vb<>'Sin apuesta'
  );

insert into tenis_api.full_analysis_hist
select * from tenis_api.main_todays_analysis
where jugador_a_apostar_cons<>'Sin apuesta' or jugador_a_apostar_vb<>'Sin apuesta';

commit;

-- select * from tenis_api.full_analysis_hist;
