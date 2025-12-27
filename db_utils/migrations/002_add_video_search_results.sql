-- Migration: Add video_search_results field to charts table
-- Version: 1.1
-- Created: 2025-12-25

-- Add video_search_results column to charts table
ALTER TABLE charts ADD COLUMN video_search_results TEXT;

