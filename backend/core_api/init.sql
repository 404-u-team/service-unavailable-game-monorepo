CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    login VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    balance INT NOT NULL DEFAULT 10000,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- Тестовые пользователи
-- login; email; password; balance
-- admin; admin@admin.com; admin123; 10000
-- bob; bob@example.com; bob123123; 5000
-- charlie; charlie@example.com; charlie123; 150000
INSERT INTO users (login, email, password_hash, balance)
VALUES
    ('admin', 'admin@admin.com', '$argon2id$v=19$m=65536,t=3,p=4$QNewl3Ait4cf4UZrp3BPDQ$pyOx2pOFQHOvUWtUGyRyamoByRjyjq8/3D0VtK92aDo', 10000),
    ('bob', 'bob@example.com', '$argon2id$v=19$m=65536,t=3,p=4$Xnr8GeoXvhm6ONru8A9+ag$gW/CV1KgOaY6bYyY/JK6Em4kqRAmmjnU2nW0+jSZCs8', 5000),
    ('charlie', 'charlie@example.com', '$argon2id$v=19$m=65536,t=3,p=4$1ez2fu44+GiOezXDtOSovg$Idhpdu1Gk4Z7jWSqpBG1qMJWLPdUiDCezQIEy2+8TTI', 150000)
ON CONFLICT DO NOTHING;