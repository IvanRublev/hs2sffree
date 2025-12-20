from sqlalchemy import create_engine, Engine, Table, Column, String, JSON, MetaData, Boolean
from typing import Tuple

metadata = MetaData()
companies = Table(
    "companies",
    metadata,
    Column("id", String, primary_key=True),
    Column("attrs", JSON, nullable=False),
    Column("name", String, index=True),
    Column("duplicate", Boolean, nullable=False, default=False, index=True),
)

DatabaseEngine = Engine


def initialize_db(path: str) -> DatabaseEngine:
    db_engine = create_engine(f"sqlite:///{path}")
    # Create all tables defined in metadata, if they are not exist
    metadata.create_all(db_engine)

    return db_engine


def close_db(db_engine: DatabaseEngine):
    db_engine.dispose()


def add_company(db_engine: DatabaseEngine, id: str, attrs: dict, name: str, duplicate: bool):
    if not attrs:
        raise ValueError("No attrs provided")

    stmt = companies.insert().values(id=id, attrs=attrs, name=name, duplicate=duplicate)
    with db_engine.begin() as conn:
        conn.execute(stmt)
        return True


def add_companies(db_engine: DatabaseEngine, id_attrs_list: list[Tuple[str, dict, str, bool]]) -> list[str | None]:
    if not id_attrs_list:
        raise ValueError("No companies provided")

    records = []
    for comp_id, attrs, name, duplicate in id_attrs_list:
        if not attrs:
            raise ValueError(f"No attrs provided for company with id {comp_id}")
        records.append({"id": comp_id, "attrs": attrs, "name": name, "duplicate": duplicate})

    stmt = companies.insert()
    with db_engine.begin() as conn:
        result = conn.execute(stmt, records)
        # extract first element of each inserted_primary_key_rows entry, or None if row is falsy
        ids = [row[0] if row else None for row in result.inserted_primary_key_rows]
        return ids


def get_company(db_engine: DatabaseEngine, id: str) -> dict:
    if not id:
        raise ValueError("No id provided")

    stmt = companies.select().with_only_columns(companies.c.attrs, companies.c.duplicate).where(companies.c.id == id)
    with db_engine.begin() as conn:
        result = conn.execute(stmt).fetchone()
        if result:
            return {"attrs": result[0], "duplicate": bool(result[1])}
        raise ValueError("Company not found")


def find_companies_by_name(db_engine: DatabaseEngine, name_list: list[str]) -> list[str | None]:
    if not name_list:
        raise ValueError("No names list provided")

    # ensure there are no duplicate names in the provided list
    seen = set()
    for name in name_list:
        if name in seen:
            raise ValueError(f'Duplicate names in list: "{name}"')
        seen.add(name)

    # order matches according to the position in name_list, then pick the first one
    stmt = (
        companies.select()
        .with_only_columns(companies.c.name, companies.c.id)
        .where(companies.c.name.in_(name_list))
        .where(companies.c.duplicate.is_(False))
    )
    with db_engine.begin() as conn:
        found_companies = conn.execute(stmt).fetchall()
        # build map from name -> id (first occurrence)
        name_to_id = {}
        for row in found_companies:
            name, id = row[0], row[1]
            name_to_id[name] = id

        # preserve order of name_list, return id or None for each name
        return [name_to_id.get(n) for n in name_list]
