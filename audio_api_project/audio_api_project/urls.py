from django.urls import path
from audio_api.views import RecordingApiView

urlpatterns = [
    path('api/record/', RecordingApiView.as_view(), name='record-audio'),
]
