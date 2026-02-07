-- Initial schema for Network Ranger
-- Migrated from MongoDB

-- Users table (Discord users)
CREATE TABLE users (
    id BIGINT PRIMARY KEY COMMENT 'Discord user ID',
    name VARCHAR(255) NOT NULL COMMENT 'Discord username',
    discriminator VARCHAR(4) COMMENT 'Legacy discriminator (deprecated by Discord)',
    nick VARCHAR(255) COMMENT 'Server nickname',
    first_joined_at DATETIME COMMENT 'First time user joined the server',
    member_number INT UNIQUE COMMENT 'Sequential member number',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_member_number (member_number),
    INDEX idx_first_joined (first_joined_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- User permanent roles (roles that persist across leave/rejoin)
CREATE TABLE user_permanent_roles (
    user_id BIGINT NOT NULL,
    role_significance VARCHAR(50) NOT NULL COMMENT 'Role significance like Member, periphery, recruiter, !eggs',
    granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_significance),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_role_significance (role_significance)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Guilds table (Discord servers)
CREATE TABLE guilds (
    id VARCHAR(50) PRIMARY KEY COMMENT 'Discord guild ID',
    name VARCHAR(255) COMMENT 'Guild name'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Guild known roles (roles with special significance)
CREATE TABLE guild_known_roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    guild_id VARCHAR(50) NOT NULL,
    role_id VARCHAR(50) NOT NULL COMMENT 'Discord role ID',
    role_name VARCHAR(255),
    color INT COMMENT 'Role color as integer',
    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
    UNIQUE KEY uk_guild_role (guild_id, role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Role significances (many-to-many: a role can have multiple significances)
CREATE TABLE role_significances (
    role_id INT NOT NULL,
    significance VARCHAR(50) NOT NULL,
    PRIMARY KEY (role_id, significance),
    FOREIGN KEY (role_id) REFERENCES guild_known_roles(id) ON DELETE CASCADE,
    INDEX idx_significance (significance)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Guild known channels (channels with special significance)
CREATE TABLE guild_known_channels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    guild_id VARCHAR(50) NOT NULL,
    channel_id VARCHAR(50) NOT NULL COMMENT 'Discord channel ID',
    significance VARCHAR(50) NOT NULL COMMENT 'Channel purpose like greeting, log, mirror',
    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
    UNIQUE KEY uk_guild_channel_sig (guild_id, channel_id, significance)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Config key-value store
CREATE TABLE config (
    name VARCHAR(100) PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
