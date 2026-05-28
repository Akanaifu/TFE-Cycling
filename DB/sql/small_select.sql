select u.display_name, uc.cyclist
from users u
join user_cyclists uc on u.id = uc.user_id;

select display_name, email, role
from users;

UPDATE users
set display_name = 'Nastia'
where email = 'nastia.rousseau@gmail.com'; 

DELETE FROM users
where email = '';

select u.display_name, u.cyclist, r.sport_type, distance_m, moving_time_s, avg_hr, avg_watts
from rides r
join users u on r.user_id = u.id
where u.cyclist = 'cyclist0';
