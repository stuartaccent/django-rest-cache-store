from django.http.response import Http404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets

from store.bindings import BaseAppStore
from store.models import StoreHistory
from store.serializers import StoreHistorySerializer


class AppStoreViewSet(viewsets.ViewSet):

    items_path = r'(?P<cache_key>[a-z]+(?:_[a-z]+)*)'
    item_path = r'(?P<cache_key>[a-z]+(?:_[a-z]+)*)/(?P<pk>\d+)'

    def list(self, request, *args, **kwargs):
        data = BaseAppStore.full_store()
        return Response(data)

    def item_cache(self, cache_key):
        try:
            return BaseAppStore.get_instance(cache_key)
        except KeyError:
            raise Http404

    @action(detail=False, methods=['get'], url_path=items_path, url_name='cache-items')
    def items(self, request, cache_key, *args, **kwargs):
        items = self.item_cache(cache_key).data()
        try:
            version = StoreHistory.objects.filter(cache_key=cache_key).latest('version').version
        except StoreHistory.DoesNotExist:
            version = BaseAppStore.get_version()
        data = {f'{cache_key}': items, 'version': version}
        return Response(data)

    @items.mapping.post
    def items_add(self, request, cache_key, *args, **kwargs):
        klass = self.item_cache(cache_key)
        return klass.create(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path=item_path, url_name='cache-item')
    def item(self, request, cache_key, pk, *args, **kwargs):
        data = self.item_cache(cache_key).cache_get(int(pk))
        return Response(data)

    @item.mapping.put
    def item_put(self, request, cache_key, pk, *args, **kwargs):
        klass = self.item_cache(cache_key)
        return klass.update(request, pk=pk, *args, **kwargs)

    @item.mapping.delete
    def item_delete(self, request, cache_key, pk, *args, **kwargs):
        klass = self.item_cache(cache_key)
        return klass.delete(request, pk=pk, *args, **kwargs)


class AppStoreHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StoreHistory.objects.all()
    serializer_class = StoreHistorySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        after = self.request.query_params.get("after", None)
        since = self.request.query_params.get("since", None)
        if after:
            qs = qs.filter(version__gt=after)
        elif since:
            qs = qs.filter(version__gte=since)
        return qs