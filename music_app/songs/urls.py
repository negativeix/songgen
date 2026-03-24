from django.urls import path
from . import views

urlpatterns = [
    path('', views.song_list),
    path('create/', views.song_create),
    path('<uuid:song_id>/update/', views.song_update),
    path('<uuid:song_id>/delete/', views.song_delete),
]