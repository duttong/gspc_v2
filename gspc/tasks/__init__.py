from gspc.schedule import register_task
from .flask import Flask
from .tank import Tank
from .zero import Zero

register_task("Flask 1", Flask(1))
register_task("Flask 3", Flask(3))
register_task("Flask 4", Flask(4))
register_task("Flask 5", Flask(5))
register_task("Flask 6", Flask(6))
register_task("Flask 7", Flask(7))
register_task("Flask 8", Flask(8))
#register_task("Flask 9", Flask(9))
register_task("Flask 10", Flask(10))
register_task("Flask 11", Flask(11))
register_task("Flask 12", Flask(12))

register_task("Tank 0", Tank(0))
register_task("Tank 2", Tank(2))
register_task("Tank 13", Tank(13))
register_task("Tank 14", Tank(13))
register_task("Tank 15", Tank(15))

register_task("Zero", Zero())
