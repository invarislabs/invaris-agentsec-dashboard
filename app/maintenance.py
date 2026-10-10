"""Housekeeping. Run on a schedule (for example daily): `python -m app.maintenance prune`."""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from .db import new_session
from .models import Project, User
from .plans import plan_named
from .reports import prune


def prune_all() -> int:
    db = new_session()
    removed = 0
    try:
        for project in db.scalars(select(Project)).all():
            owner = db.get(User, project.owner_id)
            removed += prune(db, project, plan_named(owner.plan if owner else "free"))
        db.commit()
    finally:
        db.close()
    return removed


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.maintenance")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prune", help="delete runs older than each plan's retention")
    args = p.parse_args(argv)
    if args.cmd == "prune":
        print("Removed %d expired run(s)." % prune_all())
    return 0


if __name__ == "__main__":
    sys.exit(main())
