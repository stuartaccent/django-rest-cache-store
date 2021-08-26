# Django Rest Cache Store

This is an idea ive been playing with.

## Whats it for?

In short it speeds up the retreval of an api by caching the results in djangos cache framework upfront.
All model serialization is done outside of the request which make the api as fast as it can be.

## A bit about the background

We have a large angular electron app that uses well over a 100 rest api endpoints alot of which are nested.
It uses ngrx store to pull down its data locally so it can work offline.

The problem with this is it needs to know if the data it has is still current when it comes back online.
This causes you to refetch data etc from all endpoints etc.

I also asked myself can django hold this data for me in a manner that the app needs and the app just calls
the api on say a `/store` endpoint and retrieve it in one foul swoop. Sounds mental? With that in mind
I wondered can the same single endpoint handle all the usual 'post', 'put', 'get', 'delete' actions also?

## How it works

`store.bindings.base.AppStoreMetaclass`: This has actions on it to work across all endpoints you add.
`store.bindings.base.BaseAppStore`: This is the class you should inherit from when adding what would have been a 
single `ModelViewSet` in `django-rest-framework`.

The idea is when the site first loads the cache for the entire api is built upfront using standard drf model serializers. I use `django-redis` as the cache backend.

When you call either `/store/`, `/store/items/`, `/store/items/1/` you actually bypass any queries and go directly to the cache.

So an api call on `/store/` would look like:

```python
{
    'items': [
        {'id': 1, 'name': 'foo'},
    ],
    'version': 1629381135.0730898,
}
```

Any updates are handled by post_save, and post_delete model signals which updates the store cache.

I use `huey` to perform the store updates after the model signals so no requests are waiting around.
In the situation I need to update the store outside of a model signal i just run the `huey` task manually.

## Setup

1, Add `store` to `INSTALLED_APPS`.

2, Somewhere in an apps.py

```python
class MyAppConfig(AppConfig):
    name = 'app'

    def ready(self):
        from store.bindings import BaseAppStore
        BaseAppStore.register_all()
```

3, You also need to register the routes in `urls.py` inside your api.

## Calling a full cache reload

That as simple as running the management command `./manage.py reloadstore`.

## How do you tell whats changed?

For that i created the idea of a version and history. Every update adds a row to `store.models.StoreHistory`.
Depending on what changed I can use this to tell the front end what its missed.

This can be seen at `/store/history/`.

Full store reloaded:

```python
{
    'version': 1629381132.0730898,
    'cache_key': None,
    'item_id': None,
    'state': 'F',
    'added_on': '2021-08-19 14:52:12',
}
```
Full items list reloaded:

```python
{
    'version': 1629381134.0730898,
    'cache_key': 'items',
    'item_id': None,
    'state': 'U',
    'added_on': '2021-08-19 14:52:12',
}
```

Single item reloaded:

```python
{
    'version': 1629381135.0730898,
    'cache_key': 'items',
    'item_id': 1,
    'state': 'U', // C = create, U = update, D = delete
    'added_on': '2021-08-19 14:52:12',
}
```

I can call `/store/history/?after=<version>` and tell without reloading if i need to do a full reload, single item etc.
I keep track of the current version of the store in the front-end and use that to make subsequent calls to history.

## Using websockets

I use `channels` to send the current version of the store on any change that happens. The app looks at these
and as soon as it gets a message it calls home to the history and see whats happened.

## Results

Ive gone from running over a 100 rest api calls that can take in excess of 30 seconds to an 8 second single 
full cache rebuild when I start the api and 1 api call to the store which takes about a second to pull 
down the data and handle it in the front-end. Then the odd call to subsequent updates. 

## What I haven't considered yet

- Filtering the endpoints.
- API Docs.

## Where to go from now?

I dont know, maybe I can see an endpoint that could update multiple different types of entities in one transaction. This is the main reason we have so many nested endpoints. We have to either commit or fail changes in one go.