-- Local stand-in for the Azure setup (README, step 4): one database per service, each with
-- one contained user that can reach only its own database and can run migrations
-- (db_ddladmin, db_datareader, db_datawriter). No server logins, like on Azure SQL.
-- Safe to run many times: every step checks first. Passwords come from .env via sqlcmd -v.

-- Contained users need this on a full SQL Server (Azure SQL Database always allows them)
EXEC sp_configure 'contained database authentication', 1;
RECONFIGURE;
GO

IF DB_ID('sessions') IS NULL CREATE DATABASE sessions CONTAINMENT = PARTIAL;
IF DB_ID('recordings') IS NULL CREATE DATABASE recordings CONTAINMENT = PARTIAL;
GO

USE sessions;
IF USER_ID('sessions_user') IS NULL
BEGIN
    CREATE USER sessions_user WITH PASSWORD = '$(SESSIONS_DB_PASSWORD)';
    ALTER ROLE db_ddladmin ADD MEMBER sessions_user;
    ALTER ROLE db_datareader ADD MEMBER sessions_user;
    ALTER ROLE db_datawriter ADD MEMBER sessions_user;
END
GO

USE recordings;
IF USER_ID('recordings_user') IS NULL
BEGIN
    CREATE USER recordings_user WITH PASSWORD = '$(RECORDINGS_DB_PASSWORD)';
    ALTER ROLE db_ddladmin ADD MEMBER recordings_user;
    ALTER ROLE db_datareader ADD MEMBER recordings_user;
    ALTER ROLE db_datawriter ADD MEMBER recordings_user;
END
GO
