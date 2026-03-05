from ninja import NinjaAPI
from whatsapp_inbound.api import router as inbound_router
from motor_response.api import router as motor_router

api = NinjaAPI()

api.add_router("", inbound_router)
api.add_router("", motor_router)
