from .base import BaseAppStore
from someapp.models import Item
from someapp.serializers import ItemSerializer


class ItemStore(BaseAppStore):
    cache_key = 'items'
    model = Item
    serializer = ItemSerializer
