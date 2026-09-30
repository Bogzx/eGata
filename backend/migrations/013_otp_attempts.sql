-- 013_otp_attempts.sql
--
-- Count wrong codes per OTP challenge. A wrong code used to leave the
-- challenge untouched, so a 6-digit code could be guessed for the whole
-- 5-minute TTL; only Twilio Verify's own limits applied, and none in mock
-- mode. app/auth.py burns the challenge after MAX_OTP_ATTEMPTS.

alter table otp_challenges add column if not exists attempts int not null default 0;
