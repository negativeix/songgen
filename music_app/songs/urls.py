from django.urls import path
from . import views

urlpatterns = [
    # ── Generation (Exercise 4) ──────────────────────────────────────────────
    path('generate/', views.song_generate),
    path('<uuid:song_id>/status/', views.song_status),
    path('<uuid:song_id>/cancel/', views.song_cancel),
    path('<uuid:song_id>/regenerate/', views.song_regenerate),
    path('<uuid:song_id>/visibility/', views.song_visibility),
    path('public/<uuid:token>/', views.song_public),
    path('admin/metrics/', views.admin_metrics),
    path('prompts/', views.prompt_suggestions),

    # ── Song CRUD (Exercise 3) ───────────────────────────────────────────────
    path('', views.song_list),
    path('create/', views.song_create),
    path('<uuid:song_id>/update/', views.song_update),
    path('<uuid:song_id>/delete/', views.song_delete),

    # ── User CRUD (Exercise 3) ───────────────────────────────────────────────
    path('users/', views.user_list),
    path('users/create/', views.user_create),
    path('users/<uuid:user_id>/update/', views.user_update),
    path('users/<uuid:user_id>/delete/', views.user_delete),

    # ── Folder CRUD (Exercise 3) ─────────────────────────────────────────────
    path('folders/', views.folder_list),
    path('folders/create/', views.folder_create),
    path('folders/<uuid:folder_id>/update/', views.folder_update),
    path('folders/<uuid:folder_id>/delete/', views.folder_delete),
]
