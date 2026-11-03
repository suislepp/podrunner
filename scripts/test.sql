SELECT current_user, current_database(), current_setting('server_version') AS postgres, pg_is_in_recovery() AS replica;
