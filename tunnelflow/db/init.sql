-- TunnelFlow Database Initialization Script
-- This script creates all necessary tables and initial data

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ===========================================
-- USERS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    reset_token VARCHAR(255),
    reset_token_expires TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_active ON users(is_active);

-- ===========================================
-- SUBSCRIPTION PLANS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS subscription_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) UNIQUE NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    price_usd DECIMAL(10, 2) NOT NULL DEFAULT 0,
    tunnel_limit INTEGER NOT NULL DEFAULT 1,
    traffic_limit_gb INTEGER NOT NULL DEFAULT 1,
    custom_domain_limit INTEGER NOT NULL DEFAULT 0,
    subdomain_limit INTEGER NOT NULL DEFAULT 1,
    features JSONB DEFAULT '[]'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_plans_slug ON subscription_plans(slug);
CREATE INDEX idx_plans_active ON subscription_plans(is_active);

-- ===========================================
-- USER SUBSCRIPTIONS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES subscription_plans(id),
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- active, cancelled, expired, past_due
    stripe_subscription_id VARCHAR(255) UNIQUE,
    current_period_start TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_subscriptions_user ON user_subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON user_subscriptions(status);
CREATE INDEX idx_subscriptions_plan ON user_subscriptions(plan_id);

-- ===========================================
-- TUNNELS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS tunnels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    token VARCHAR(255) UNIQUE NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    local_host VARCHAR(255) DEFAULT 'localhost',
    local_port INTEGER NOT NULL,
    protocol VARCHAR(20) DEFAULT 'http', -- http, https, tls
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_connected_at TIMESTAMP WITH TIME ZONE,
    connection_count INTEGER DEFAULT 0,
    total_bytes_sent BIGINT DEFAULT 0,
    total_bytes_received BIGINT DEFAULT 0
);

CREATE INDEX idx_tunnels_user ON tunnels(user_id);
CREATE INDEX idx_tunnels_token ON tunnels(token);
CREATE INDEX idx_tunnels_active ON tunnels(is_active);
CREATE INDEX idx_tunnels_protocol ON tunnels(protocol);

-- ===========================================
-- DOMAINS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS domains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tunnel_id UUID REFERENCES tunnels(id) ON DELETE SET NULL,
    domain_name VARCHAR(255) UNIQUE NOT NULL,
    domain_type VARCHAR(20) NOT NULL DEFAULT 'subdomain', -- subdomain, custom
    is_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    ssl_enabled BOOLEAN DEFAULT TRUE,
    ssl_status VARCHAR(20) DEFAULT 'pending', -- pending, active, failed, renewing
    ssl_expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    verified_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_domains_user ON domains(user_id);
CREATE INDEX idx_domains_tunnel ON domains(tunnel_id);
CREATE INDEX idx_domains_name ON domains(domain_name);
CREATE INDEX idx_domains_type ON domains(domain_type);

-- ===========================================
-- INVOICES TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES user_subscriptions(id) ON DELETE SET NULL,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    amount_usd DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, paid, failed, cancelled, refunded
    stripe_invoice_id VARCHAR(255) UNIQUE,
    stripe_payment_intent_id VARCHAR(255),
    pdf_url VARCHAR(500),
    due_date TIMESTAMP WITH TIME ZONE,
    paid_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_invoices_user ON invoices(user_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_number ON invoices(invoice_number);

-- ===========================================
-- USAGE LOGS TABLE (for billing & analytics)
-- ===========================================
CREATE TABLE IF NOT EXISTS usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tunnel_id UUID REFERENCES tunnels(id) ON DELETE SET NULL,
    log_date DATE NOT NULL,
    bytes_sent BIGINT NOT NULL DEFAULT 0,
    bytes_received BIGINT NOT NULL DEFAULT 0,
    request_count INTEGER NOT NULL DEFAULT 0,
    unique_visitors INTEGER NOT NULL DEFAULT 0,
    avg_response_time_ms INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, tunnel_id, log_date)
);

CREATE INDEX idx_usage_user_date ON usage_logs(user_id, log_date);
CREATE INDEX idx_usage_tunnel_date ON usage_logs(tunnel_id, log_date);
CREATE INDEX idx_usage_date ON usage_logs(log_date);

-- ===========================================
-- API TOKENS TABLE (for programmatic access)
-- ===========================================
CREATE TABLE IF NOT EXISTS api_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    prefix VARCHAR(10) NOT NULL, -- For display purposes (e.g., tf_abc123...)
    scopes JSONB DEFAULT '["read"]'::jsonb,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_api_tokens_user ON api_tokens(user_id);
CREATE INDEX idx_api_tokens_hash ON api_tokens(token_hash);

-- ===========================================
-- AUDIT LOGS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    ip_address INET,
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_created ON audit_logs(created_at);

-- ===========================================
-- SYSTEM METRICS TABLE (for real-time monitoring)
-- ===========================================
CREATE TABLE IF NOT EXISTS system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(20, 6) NOT NULL,
    unit VARCHAR(20),
    labels JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_name_time ON system_metrics(metric_name, timestamp DESC);
CREATE INDEX idx_metrics_time ON system_metrics(timestamp DESC);

-- ===========================================
-- INSERT DEFAULT SUBSCRIPTION PLANS
-- ===========================================
INSERT INTO subscription_plans (name, slug, price_usd, tunnel_limit, traffic_limit_gb, custom_domain_limit, subdomain_limit, features) VALUES
('Free', 'free', 0.00, 1, 1, 0, 1, '["Basic HTTP tunnels", "Shared subdomains", "Community support"]'::jsonb),
('Starter', 'starter', 5.00, 3, 20, 1, 3, '["Custom domains", "HTTPS/SSL", "Email support", "Basic stats"]'::jsonb),
('Pro', 'pro', 15.00, 10, 100, 5, 10, '["Priority support", "Advanced analytics", "Webhooks", "API access"]'::jsonb),
('Business', 'business', 50.00, 50, 500, 20, 50, '["SLA guarantee", "Dedicated support", "Custom integrations", "White-label"]'::jsonb),
('Enterprise', 'enterprise', 0.00, 999999, 999999, 999999, 999999, '["Unlimited everything", "24/7 phone support", "Custom contract", "On-premise option"]'::jsonb)
ON CONFLICT (slug) DO NOTHING;

-- ===========================================
-- CREATE UPDATED_AT TRIGGER FUNCTION
-- ===========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to tables with updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscriptions_updated_at BEFORE UPDATE ON user_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tunnels_updated_at BEFORE UPDATE ON tunnels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_invoices_updated_at BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ===========================================
-- COMMENTS FOR DOCUMENTATION
-- ===========================================
COMMENT ON TABLE users IS 'User accounts with authentication';
COMMENT ON TABLE subscription_plans IS 'Available subscription tiers';
COMMENT ON TABLE user_subscriptions IS 'Active user subscriptions';
COMMENT ON TABLE tunnels IS 'User-created tunnels for port forwarding';
COMMENT ON TABLE domains IS 'Custom and subdomain assignments';
COMMENT ON TABLE invoices IS 'Billing invoices';
COMMENT ON TABLE usage_logs IS 'Daily usage statistics per tunnel';
COMMENT ON TABLE api_tokens IS 'API access tokens for automation';
COMMENT ON TABLE audit_logs IS 'Security and activity audit trail';
COMMENT ON TABLE system_metrics IS 'Real-time system performance metrics';
