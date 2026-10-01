-- The HoloGraph dump predates this PHPRetro installer. Its users table has
-- legacy NOT NULL columns that the installer intentionally leaves implicit.
-- Relax only this disposable database so the original installer can create
-- its synthetic administrator row and the CMS row can share its id.
ALTER TABLE users
  MODIFY tickets int(5) NULL DEFAULT 0,
  MODIFY badge_status enum('0','1') NULL DEFAULT '1',
  MODIFY lastvisit varchar(50) NULL,
  MODIFY figure_swim varchar(100) NULL,
  MODIFY user text NULL,
  MODIFY postcount bigint(20) NULL DEFAULT 0,
  MODIFY ticket_sso varchar(39) NULL,
  MODIFY ipaddress_last varchar(100) NULL,
  MODIFY noob int(1) NULL DEFAULT 0,
  MODIFY online mediumint(30) NULL DEFAULT 1,
  MODIFY bb_totalpoints int(30) NULL DEFAULT 0,
  MODIFY bb_playedgames int(30) NULL DEFAULT 0,
  MODIFY screen varchar(100) NULL,
  MODIFY rea varchar(100) NULL,
  MODIFY gift smallint(2) NULL,
  MODIFY sort smallint(1) NULL,
  MODIFY roomid int(15) NULL,
  MODIFY lastgift smallint(2) NULL,
  MODIFY visibility int(1) NULL DEFAULT 1,
  MODIFY hc_before int(1) NULL,
  MODIFY guideavailable int(1) NULL DEFAULT 0,
  MODIFY shockwaveid text NULL,
  MODIFY guide int(1) NULL DEFAULT 0,
  MODIFY `guide-allowed` int(1) NULL DEFAULT 0,
  MODIFY `window` int(3) NULL DEFAULT 0;
