from app import routers
from store.views import *


# app router
router = routers.DefaultRouter()

# api routes
router.register(r'store/history', AppStoreHistoryViewSet, basename='storehistory')
router.register(r'store', AppStoreViewSet, basename='store')
