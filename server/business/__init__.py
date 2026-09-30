"""The business layer: people and companies, sales, projects, tasks, calendar, notes, files, catalogue, Today, timeline, import, demo.

`register()` runs before the data is opened (entities and permissions); `routes(app)` adds the API routes to the router.
The core (server/core) never imports this package."""


def register():
    from . import entities, perms
    perms.register_all()
    entities.register_all()


def routes(app):
    from . import api
    api.add_routes(app)
