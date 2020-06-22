#!/usr/bin/env python

import argparse
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager


load_dotenv()


NAMES_SQL = """
SELECT DISTINCT LOWER(name) AS name
FROM (
	SELECT SURNAME AS name
	FROM DWREPO.dbo.PATIENT
	UNION
	SELECT LEFT(forenames, PATINDEX('%[ -/]%', forenames + ' ') - 1) AS name
	FROM DWREPO.dbo.PATIENT
) x
WHERE name IS NOT NULL
	AND LEN(name) > 2
ORDER BY LOWER(name)
;
"""


@contextmanager
def databases_engine():

  driver = os.environ["MS_SQL_ODBC_DRIVER"]
  username = os.environ["MS_SQL_UHL_DWH_USER"]
  password = os.environ["MS_SQL_UHL_DWH_PASSWORD"]
  host = os.environ["MS_SQL_UHL_DWH_HOST"]
  database = os.environ["MS_SQL_UHL_DWH_DATABASE"]
  database_echo = os.environ["DATABASE_ECHO"] == 'True'

  connectionstring = f'mssql+pyodbc://{username}:{password}@{host}/{database}?driver={driver.replace(" ", "+")}'
  engine = create_engine(connectionstring, echo=database_echo)
  yield engine
  engine.dispose()


def main():
  with databases_engine() as conn:
    names = {r for r, in conn.execute(NAMES_SQL)}

  with open("_names.txt", "w") as outfile:
      outfile.write("\n".join(names))

if __name__ == "__main__":
  main()