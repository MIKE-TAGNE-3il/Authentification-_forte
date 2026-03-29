-- ═══════════════════════════════════════════════════════════════════════════
--  AuthForte — Initialisation MySQL
--  Exécuté automatiquement par le conteneur MySQL au premier démarrage.
--  Les tables sont créées par Flask (init_database_schema, etc.) au boot.
--  Ce script crée uniquement la base + les droits utilisateur.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS `authentification` 
    CHARACTER SET utf8mb4 
    COLLATE utf8mb4_general_ci;

USE `authentification`;

-- Table des utilisateurs
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `nom` VARCHAR(255) NOT NULL,
    `email` VARCHAR(255) NOT NULL UNIQUE,
    `password` VARCHAR(255) NOT NULL,
    `webauthn_credential_id` BLOB,
    `webauthn_public_key` BLOB,
    `webauthn_sign_count` INT DEFAULT 0,
    `createdAt` DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Table spécifique YubiKey (FIDO2/WebAuthn)
CREATE TABLE IF NOT EXISTS `yubikey` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `userId` INT NOT NULL,
    `credentialId` BLOB NOT NULL,
    `publicKey` BLOB NOT NULL,
    `signCount` INT UNSIGNED NOT NULL DEFAULT 0,
    `label` VARCHAR(255) DEFAULT 'Ma YubiKey',
    `createdAt` DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_yubikey_user` FOREIGN KEY (`userId`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Droits d'accès
GRANT ALL PRIVILEGES ON `authentification`.* TO 'authforte'@'%';
FLUSH PRIVILEGES;
