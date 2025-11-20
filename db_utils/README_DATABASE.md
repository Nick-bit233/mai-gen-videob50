# Database Schema Management

This directory contains the database schema and migration files for the mai-gen-videob50 project.

## Files

- `schema.sql` - Complete database schema for fresh installations
- `migrations/` - Directory containing database migration files

## Schema Versioning

The database now includes a `schema_version` table that tracks the current schema version and applied migrations. This allows for safe database updates without losing existing data.

## Using Migrations

### Creating a New Migration

1. Create a new SQL file in the `migrations/` directory with a descriptive name:
   ```
   migrations/002_add_new_feature.sql
   ```

2. Include a header comment with migration details:
   ```sql
   -- Migration: Add new feature
   -- Version: 1.2
   -- Description: Adds support for new feature X
   ```

3. Write your migration SQL statements

### Applying Migrations

Use the `DatabaseManager.apply_migration()` method to apply a specific migration:

```python
db = DatabaseManager()
db.apply_migration('002_add_new_feature.sql')
db.update_schema_version('1.2', 'Added new feature X')
```

### Checking Schema Version

```python
db = DatabaseManager()
current_version = db.get_schema_version()
print(f"Current schema version: {current_version}")
```

## Best Practices

1. **Never modify existing migrations** - Once a migration has been applied, create a new migration to make changes
2. **Test migrations thoroughly** - Always test migrations on a copy of your database first
3. **Use descriptive names** - Migration files should clearly describe what they do
4. **Include rollback information** - Document how to undo changes if needed
5. **Version incrementally** - Use semantic versioning (1.0, 1.1, 1.2, etc.)

## Schema Updates

When updating the main `schema.sql` file:

1. Update the version number in the INSERT statement at the end
2. Document changes in the migration history
3. Test that fresh installations work correctly
4. Create corresponding migration files for existing databases

## Example Migration Workflow

1. Current database is at version 1.0
2. Need to add a new column to the `users` table
3. Create `migrations/002_add_user_preferences.sql`:
   ```sql
   -- Migration: Add user preferences column
   -- Version: 1.1
   -- Description: Add preferences JSON column to users table
   
   ALTER TABLE users ADD COLUMN preferences TEXT DEFAULT '{}';
   ```
4. Apply the migration:
   ```python
   db.apply_migration('002_add_user_preferences.sql')
   db.update_schema_version('1.1', 'Added user preferences column')
   ```
5. Update `schema.sql` to include the new column for fresh installations
