--- query 05
-- insert full analysis into historical analysis table


----- CREATE INITIAL
-- refresh materialized view tenis_api.main_todays_analysis;
-- drop table tenis_api.full_analysis_hist;
-- create table tenis_api.full_analysis_hist as
-- select * from tenis_api.main_todays_analysis
-- where jugador_a_apostar_cons<>'Sin apuesta' or jugador_a_apostar_vb<>'Sin apuesta';


-- -- select * from tenis_api.full_analysis_hist;
-- select * from tenis_api.full_analysis_hist ORDER BY 1;
-- select event_date, count(*) from tenis_api.full_analysis_hist group by 1 ORDER by 1;



---- DAILY INSERT

BEGIN;


refresh materialized view tenis_api.main_todays_analysis;

-- Step 1: UPDATE past records (only refresh event_winner & bet_result)

WITH calc AS (
    SELECT
        s.event_key,
        s.event_date,
        s.event_winner,
        s.p1_odds,
        s.p2_odds,
        h.jugador_a_apostar_cons,
        h.jugador_a_apostar_vb,
        h.event_first_player,
        h.event_second_player,
        h.monto_apuesta_vb,
        h.monto_apuesta_cons,
        -- Pre-calculate result_bet so it can be reused below
        CASE
            WHEN h.jugador_a_apostar_cons = 'Sin apuesta'                                   THEN null
            WHEN h.jugador_a_apostar_cons = h.event_first_player  AND s.event_winner = 'P1' THEN 'won'
            WHEN h.jugador_a_apostar_cons = h.event_second_player AND s.event_winner = 'P2' THEN 'won'
            WHEN h.jugador_a_apostar_cons = h.event_first_player  AND s.event_winner = 'P2' THEN 'lost'
            WHEN h.jugador_a_apostar_cons = h.event_second_player AND s.event_winner = 'P1' THEN 'lost'
            WHEN h.jugador_a_apostar_cons IN (h.event_first_player, h.event_second_player)
                 AND s.event_winner IS NULL                                                  THEN 'unkn'
            ELSE 'check'
        END AS result_bet
    FROM tenis_api.main_todays_analysis s
    JOIN tenis_api.full_analysis_hist h
      ON h.event_key  = s.event_key
     AND h.event_date = s.event_date
    WHERE h.event_date::date < current_date
--      AND (s.jugador_a_apostar_cons <> 'Sin apuesta' OR s.jugador_a_apostar_vb <> 'Sin apuesta')
) --select * from calc
UPDATE tenis_api.full_analysis_hist h
SET
    event_winner    = c.event_winner,
    result_bet      = c.result_bet,
    p1_odds         = c.p1_odds,
    p2_odds         = c.p2_odds,
    profit_loss_vb  = CASE
                        WHEN c.jugador_a_apostar_vb = c.event_first_player  AND c.result_bet = 'won'  THEN round(c.monto_apuesta_vb * (c.p1_odds - 1), 2)
                        WHEN c.jugador_a_apostar_vb = c.event_second_player AND c.result_bet = 'won'  THEN round(c.monto_apuesta_vb * (c.p2_odds - 1), 2)
                        WHEN c.jugador_a_apostar_vb = c.event_first_player  AND c.result_bet = 'lost' THEN round(-1 * c.monto_apuesta_vb, 2)
                        WHEN c.jugador_a_apostar_vb = c.event_second_player AND c.result_bet = 'lost' THEN round(-1 * c.monto_apuesta_vb, 2)
                      END,
    profit_loss_cons = CASE
                        WHEN c.jugador_a_apostar_cons = c.event_first_player  AND c.result_bet = 'won'  THEN round(c.monto_apuesta_cons * (c.p1_odds - 1), 2)
                        WHEN c.jugador_a_apostar_cons = c.event_second_player AND c.result_bet = 'won'  THEN round(c.monto_apuesta_cons * (c.p2_odds - 1), 2)
                        WHEN c.jugador_a_apostar_cons = c.event_first_player  AND c.result_bet = 'lost' THEN round(-1 * c.monto_apuesta_cons, 2)
                        WHEN c.jugador_a_apostar_cons = c.event_second_player AND c.result_bet = 'lost' THEN round(-1 * c.monto_apuesta_cons, 2)
                      END
FROM calc c
WHERE h.event_key  = c.event_key
  AND h.event_date = c.event_date;
  
 
-- Step 2: DELETE future/today records (full refresh needed)
DELETE FROM tenis_api.full_analysis_hist
WHERE event_date IN (
    SELECT event_date
    FROM tenis_api.main_todays_analysis
    WHERE 
    -- (jugador_a_apostar_cons <> 'Sin apuesta' OR jugador_a_apostar_vb <> 'Sin apuesta')
    --   AND 
      event_date::date >= current_date
);

-- Step 3: INSERT future/today records
INSERT INTO tenis_api.full_analysis_hist
SELECT *
FROM tenis_api.main_todays_analysis
WHERE (jugador_a_apostar_cons <> 'Sin apuesta' OR jugador_a_apostar_vb <> 'Sin apuesta')
  AND event_date::date >= current_date;

COMMIT;

-- select * from tenis_api.full_analysis_hist;
