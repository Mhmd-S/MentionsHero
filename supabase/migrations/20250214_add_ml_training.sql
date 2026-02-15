-- ML Training Jobs table
CREATE TABLE ml_training_jobs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending',
  -- pending → preparing_data → training → evaluating → completed / failed / cancelled
  stage_progress JSONB DEFAULT '{}',
  error_message TEXT,
  total_segments INTEGER DEFAULT 0,
  train_segments INTEGER DEFAULT 0,
  valid_segments INTEGER DEFAULT 0,
  test_segments INTEGER DEFAULT 0,
  config JSONB DEFAULT '{}',
  adapter_path TEXT,
  data_path TEXT,
  final_train_loss NUMERIC,
  final_valid_loss NUMERIC,
  training_duration_seconds INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  cancel_requested BOOLEAN DEFAULT false
);

-- Add ML model columns to personas
ALTER TABLE personas ADD COLUMN last_trained_at TIMESTAMPTZ;
ALTER TABLE personas ADD COLUMN has_model BOOLEAN DEFAULT false;
