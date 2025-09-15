# Data Populators

This folder contains scripts to seed the database with initial or sample data used during development and testing.

## Pages

Populate CMS-like pages from `populate_data/data/pages.json`.

- Create pages (skip existing):
  
  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/populate_pages.py
  ```

- Create or update existing pages (upsert by `unique_name`):
  
  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/populate_pages.py --update
  ```

- Clear all pages:
  
  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/populate_pages.py --clear
  ```

- Use a custom JSON file:
  
  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/populate_pages.py --file path/to/pages.json
  ```

Notes:
- Pages are identified by `unique_name` and created if missing. With `--update`, existing pages are updated in-place.
- Ensure your database is running and `ASYNC_DATABASE_URL` is configured in `.env`.
