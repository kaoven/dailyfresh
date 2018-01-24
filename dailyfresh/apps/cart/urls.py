from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from .views import CartAddView, CartInfoView, CartUpdateView, CartDeleteView

urlpatterns = [
    url(r'^add', CartAddView.as_view(), name='add'),
    url(r'^$', login_required(CartInfoView.as_view()), name='show'),
    url(r'^update', CartUpdateView.as_view(), name='update'),
    url(r'^delete', CartDeleteView.as_view(), name='delete'),
]
