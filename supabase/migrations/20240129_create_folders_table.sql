-- Create folders table for hierarchical organization
CREATE TABLE folders (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  parent_id UUID REFERENCES folders(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT unique_folder_name_per_parent UNIQUE (parent_id, name)
);

-- Create index for faster parent lookups
CREATE INDEX idx_folders_parent_id ON folders(parent_id);
