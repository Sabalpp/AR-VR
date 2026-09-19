import os
import tempfile

# Never use an application database for destructive test fixtures.
os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(prefix="reach-tests-", suffix=".db")
