-- Add core models: BugReport, Page, AppUpdate
-- Migration: 20250114000000_add_core_models

BEGIN;

-- Create bug_type enum
CREATE TYPE bug_type AS ENUM ('ui_bug', 'functionality_bug', 'performance_issue', 'crash', 'feature_request', 'other');

-- Create bug_severity enum
CREATE TYPE bug_severity AS ENUM ('low', 'medium', 'high', 'critical');

-- Create bug_status enum
CREATE TYPE bug_status AS ENUM ('open', 'in_progress', 'resolved', 'closed');

-- Create page_format enum
CREATE TYPE page_format AS ENUM ('html', 'markdown', 'json');

-- Create bug_reports table
CREATE TABLE bug_reports (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    source VARCHAR(50) NOT NULL,
    bug_type bug_type NOT NULL,
    severity bug_severity NOT NULL,
    status bug_status DEFAULT 'open',
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    steps_to_reproduce TEXT,
    expected_behavior TEXT,
    actual_behavior TEXT,
    device_info JSONB,
    app_version VARCHAR(50),
    media_urls JSONB,
    tags JSONB,
    assigned_to INTEGER REFERENCES users(id),
    resolution TEXT,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create pages table
CREATE TABLE pages (
    id SERIAL PRIMARY KEY,
    unique_name VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    format page_format DEFAULT 'html',
    custom_config JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    is_draft BOOLEAN DEFAULT FALSE,
    created_by INTEGER REFERENCES users(id),
    updated_by INTEGER REFERENCES users(id),
    view_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create app_updates table
CREATE TABLE app_updates (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,
    version VARCHAR(20) NOT NULL,
    build_number INTEGER,
    release_notes TEXT,
    download_url VARCHAR(500),
    is_mandatory BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    min_supported_version VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_bug_reports_user_id ON bug_reports(user_id);
CREATE INDEX idx_bug_reports_status ON bug_reports(status);
CREATE INDEX idx_bug_reports_bug_type ON bug_reports(bug_type);
CREATE INDEX idx_bug_reports_created_at ON bug_reports(created_at);

CREATE INDEX idx_pages_unique_name ON pages(unique_name);
CREATE INDEX idx_pages_is_active ON pages(is_active);
CREATE INDEX idx_pages_is_draft ON pages(is_draft);

CREATE INDEX idx_app_updates_platform ON app_updates(platform);
CREATE INDEX idx_app_updates_is_active ON app_updates(is_active);
CREATE INDEX idx_app_updates_created_at ON app_updates(created_at);

-- Add trigger for updated_at timestamp on bug_reports
CREATE OR REPLACE FUNCTION update_bug_reports_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_bug_reports_updated_at
    BEFORE UPDATE ON bug_reports
    FOR EACH ROW
    EXECUTE FUNCTION update_bug_reports_updated_at();

-- Add trigger for updated_at timestamp on pages
CREATE OR REPLACE FUNCTION update_pages_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_pages_updated_at
    BEFORE UPDATE ON pages
    FOR EACH ROW
    EXECUTE FUNCTION update_pages_updated_at();

-- Add trigger for updated_at timestamp on app_updates
CREATE OR REPLACE FUNCTION update_app_updates_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_app_updates_updated_at
    BEFORE UPDATE ON app_updates
    FOR EACH ROW
    EXECUTE FUNCTION update_app_updates_updated_at();

COMMIT;
