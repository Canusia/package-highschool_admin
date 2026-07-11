from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseNotFound, FileResponse

from cis.models.highschool import HighSchoolTranscript
from cis.menu import draw_menu
from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang

from .utils import get_user_highschools, get_hsadmin_menu


def transcripts(request):
    """Transcripts list page."""
    return render(
        request,
        'highschool_admin/transcripts.html',
        {
            'menu': draw_menu(get_hsadmin_menu(), 'transcripts', '', 'highschool_admin'),
            'intro': portal_lang(request).from_db().get('transcripts_blurb', 'Change me'),
        })


def get_transcripts(request):
    """JSON API endpoint for transcripts list."""
    highschools = get_user_highschools(request)

    # Get all high school transcripts
    transcripts_qs = HighSchoolTranscript.objects.filter(
        highschool__in=highschools
    )

    result = {
        'data': []
    }
    for record in transcripts_qs:
        result['data'].append({
            'uploaded_on': record.uploaded_on.strftime('%m/%d/%Y') if record.uploaded_on else '',
            'id': record.id,
            'uploaded_by': f'{record.uploaded_by.last_name}, {record.uploaded_by.first_name}',
            'highschool': record.highschool.name,
            'description': record.description,
            'media': record.media.url,
            'file_name': record.file_name
        })
    return JsonResponse(result)


def download_transcript(request, record_id):
    """Download a transcript file."""
    file = get_object_or_404(
        HighSchoolTranscript,
        pk=record_id
    )

    highschools = get_user_highschools(request)

    if file.highschool not in highschools:
        return HttpResponseNotFound('File not found')

    from cis.backends.storage_backend import PrivateMediaStorage

    media_storage = PrivateMediaStorage()
    response = FileResponse(
        media_storage.open(str(file.media), 'rb'),
        content_type='application/force-download'
    )

    response['Content-Disposition'] = f'attachment; filename="{file.file_name}"'
    return response
