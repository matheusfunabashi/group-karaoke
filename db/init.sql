-- Safe to run many times: every step checks first.
IF DB_ID('sessions') IS NULL CREATE DATABASE sessions;
IF DB_ID('recordings') IS NULL CREATE DATABASE recordings;
GO

IF SUSER_ID('sessions_user') IS NULL
    CREATE LOGIN sessions_user WITH PASSWORD = '$(SESSIONS_DB_PASSWORD)';
IF SUSER_ID('recordings_user') IS NULL
    CREATE LOGIN recordings_user WITH PASSWORD = '$(RECORDINGS_DB_PASSWORD)';
GO

USE sessions;
IF USER_ID('sessions_user') IS NULL
BEGIN
    CREATE USER sessions_user FOR LOGIN sessions_user;
    ALTER ROLE db_owner ADD MEMBER sessions_user;
END
GO

USE recordings;
IF USER_ID('recordings_user') IS NULL
BEGIN
    CREATE USER recordings_user FOR LOGIN recordings_user;
    ALTER ROLE db_owner ADD MEMBER recordings_user;
END
GO