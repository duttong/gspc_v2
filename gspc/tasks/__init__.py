from gspc.schedule import register_task
from .tank import Tank
from .flask import Flask

register_task("Tank 1", Tank(1))
register_task("Tank 2", Tank(2))
register_task("Tank 3", Tank(3))
register_task("Tank 4", Tank(4))

register_task("Flask 1", Flask(1))
register_task("Flask 2", Flask(2))
register_task("Flask 3", Flask(3))
register_task("Flask 4", Flask(4))
