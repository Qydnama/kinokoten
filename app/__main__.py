from app.main import main
from app.persistence.migrations import upgrade_database

upgrade_database()
main()
