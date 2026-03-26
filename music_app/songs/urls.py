from django.urls import path
from . import views

urlpatterns = [
    # Song
    path('', views.song_list),
    path('create/', views.song_create),
    path('<uuid:song_id>/update/', views.song_update),
    path('<uuid:song_id>/delete/', views.song_delete),

    # User
    path('users/', views.user_list),
    path('users/create/', views.user_create),
    path('users/<uuid:user_id>/update/', views.user_update),
    path('users/<uuid:user_id>/delete/', views.user_delete),
    
    # Folder
    path('folders/', views.folder_list),
    path('folders/create/', views.folder_create),
    path('folders/<uuid:folder_id>/update/', views.folder_update),
    path('folders/<uuid:folder_id>/delete/', views.folder_delete),
]