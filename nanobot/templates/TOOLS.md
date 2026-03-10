# Tool Usage Notes

Tool signatures are provided automatically via function calling.
This file documents non-obvious constraints and usage patterns.

## exec — Safety Limits

- Commands have a configurable timeout (default 60s)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters
- `restrictToWorkspace` config can limit file access to the workspace

## cron — Scheduled Reminders

- Please refer to cron skill for usage.

## image_inspect — Image Understanding

- Use `image_inspect` for local image files (png/jpg/jpeg/webp/gif/bmp)
- Prefer it over `read_file` when user asks to describe or analyze an image
- Pass the image path and a concise question
