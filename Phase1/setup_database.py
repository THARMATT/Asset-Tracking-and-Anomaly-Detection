
# ==========================================
# DATABASE SETUP
# ==========================================

from database import (
    create_tables,
    insert_assets,
    insert_authorization
)


print("=" * 45)
print("       DATABASE SETUP")
print("=" * 45)

print("\nCreating database tables...")
create_tables()

print("\nAdding sample assets...")
insert_assets()

print("\nAdding authorization records...")
insert_authorization()

print("\n" + "=" * 45)
print("     DATABASE SETUP COMPLETED")
print("=" * 45)
