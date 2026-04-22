from django.contrib import admin
from django.urls import path, include
from songs.page_views import (
    landing_view, library_view, generate_view,
    song_detail_view, public_share_page_view, how_to_view,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── Google OAuth (allauth) ───────────────────────────────────────────────
    path('accounts/', include('allauth.urls')),

    # ── Frontend pages ───────────────────────────────────────────────────────
    path('', landing_view, name='landing'),
    path('library/', library_view, name='library'),
    path('generate/', generate_view, name='generate'),
    path('song/<uuid:song_id>/', song_detail_view, name='song_detail'),
    path('share/<uuid:token>/', public_share_page_view, name='public_share'),
    path('how-to/', how_to_view, name='how_to'),

    # ── JSON API (Exercise 4) ────────────────────────────────────────────────
    path('songs/', include('songs.urls')),
]
