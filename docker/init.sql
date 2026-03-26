-- ═══════════════════════════════════════════════════════════════════════════
--  AuthForte — Initialisation MySQL
--  Exécuté automatiquement par le conteneur MySQL au premier démarrage.
--  Les tables sont créées par Flask (init_database_schema, etc.) au boot.
--  Ce script crée uniquement la base + les droits utilisateur.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS `authentification`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;

-- L'utilisateur est créé via les variables MYSQL_USER / MYSQL_PASSWORD
-- (gérées par l'image officielle mysql:8.0).
-- On lui accorde tous les droits sur la base applicative.
GRANT ALL PRIVILEGES ON `authentification`.* TO 'authforte'@'%';
FLUSH PRIVILEGES;
